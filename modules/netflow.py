"""
NetFlow Collector Module
Receives and parses NetFlow v5 and v9 flow records over UDP.

Default listen port: 2055  (also common: 9995, 9996)

Supported:
  - NetFlow v5  — fixed 48-byte records, full field parsing
  - NetFlow v9  — template-based; stores templates per (exporter, source_id)
                  and decodes data flowsets once the matching template arrives
"""

import socket
import struct
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from .logger import get_observability_manager

# ── Protocol number → name ────────────────────────────────────────────────────
PROTO_NAMES: Dict[int, str] = {
    1: "ICMP", 6: "TCP", 17: "UDP", 47: "GRE",
    50: "ESP", 51: "AH", 89: "OSPF", 132: "SCTP",
}

# ── NetFlow v5 binary formats ─────────────────────────────────────────────────
#   Header  (24 bytes):  version count uptime secs nsecs seq eng_type eng_id sampling
_NF5_HDR_FMT  = "!HHIIIIBBH"
_NF5_HDR_SIZE = struct.calcsize(_NF5_HDR_FMT)   # 24

#   Record  (48 bytes):  srcaddr dstaddr nexthop input output
#                        dPkts dOctets first last srcport dstport
#                        pad1 tcp_flags prot tos src_as dst_as src_mask dst_mask pad2
_NF5_REC_FMT  = "!4s4s4sHHIIIIHHBBBBHHBBH"
_NF5_REC_SIZE = struct.calcsize(_NF5_REC_FMT)   # 48

# ── NetFlow v9 binary formats ─────────────────────────────────────────────────
#   Header  (20 bytes):  version count uptime secs pkg_seq source_id
_NF9_HDR_FMT  = "!HHIIII"
_NF9_HDR_SIZE = struct.calcsize(_NF9_HDR_FMT)   # 20

#   Flowset header (4 bytes):  flowset_id  length
_NF9_FS_HDR_FMT  = "!HH"
_NF9_FS_HDR_SIZE = struct.calcsize(_NF9_FS_HDR_FMT)  # 4

# Common v9 field type IDs we decode
_NF9_FIELDS = {
    1:  ("in_bytes",    "I"),   # bytes in
    2:  ("in_pkts",     "I"),   # packets in
    4:  ("protocol",    "B"),   # IP protocol number
    7:  ("src_port",    "H"),   # L4 source port
    8:  ("src_addr",    "4s"),  # IPv4 source address
    11: ("dst_port",    "H"),   # L4 destination port
    12: ("dst_addr",    "4s"),  # IPv4 destination address
    21: ("last_sw",     "I"),   # last switched (ms since boot)
    22: ("first_sw",    "I"),   # first switched (ms since boot)
    23: ("out_bytes",   "I"),   # bytes out
    24: ("out_pkts",    "I"),   # packets out
}

# Maximum flows kept in the in-memory circular buffer
_MAX_FLOWS = 10_000


def _proto_name(num: int) -> str:
    return PROTO_NAMES.get(num, str(num))


def _ip(raw: bytes) -> str:
    return socket.inet_ntoa(raw)


class NetFlowCollector:
    """
    UDP listener that parses NetFlow v5 / v9 packets and stores the
    decoded flow records in a thread-safe circular buffer.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 2055):
        self.host = host
        self.port = port
        self.logger = get_observability_manager()

        self._flows: deque = deque(maxlen=_MAX_FLOWS)
        self._lock = threading.Lock()

        # v9 template cache: {(exporter_ip, source_id, template_id): [field_defs]}
        # field_defs = [(name, fmt_char, length), ...]
        self._v9_templates: Dict[Tuple, List] = {}

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._sock: Optional[socket.socket] = None

        # Counters
        self.stats = {
            "packets_received": 0,
            "flows_decoded":    0,
            "v5_packets":       0,
            "v9_packets":       0,
            "parse_errors":     0,
        }

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> Tuple[bool, str]:
        """Bind the UDP socket and start the collector thread."""
        if self._thread and self._thread.is_alive():
            return False, f"Collector already running on port {self.port}"
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.settimeout(1.0)
            self._sock.bind((self.host, self.port))

            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._listen_loop, daemon=True, name="netflow-collector"
            )
            self._thread.start()

            self.logger.log_event(
                "netflow_started", None,
                f"NetFlow collector listening on {self.host}:{self.port}",
                status="success",
            )
            return True, f"NetFlow collector started on port {self.port}"

        except OSError as exc:
            return False, f"Failed to bind port {self.port}: {exc}"

    def stop(self) -> Tuple[bool, str]:
        """Stop the collector thread and close the socket."""
        if not self._thread or not self._thread.is_alive():
            return False, "Collector is not running"

        self._stop_event.set()
        self._thread.join(timeout=3)
        if self._sock:
            self._sock.close()
            self._sock = None

        self.logger.log_event(
            "netflow_stopped", None,
            f"NetFlow collector stopped (port {self.port})",
            status="info",
        )
        return True, "NetFlow collector stopped"

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    # ── Listener loop ─────────────────────────────────────────────────────────

    def _listen_loop(self):
        while not self._stop_event.is_set():
            try:
                data, addr = self._sock.recvfrom(65535)
                exporter_ip = addr[0]
                self.stats["packets_received"] += 1
                self._dispatch(data, exporter_ip)
            except socket.timeout:
                continue
            except Exception as exc:
                if not self._stop_event.is_set():
                    self.logger.log_error(None, str(exc), "netflow_recv_error")
                    self.stats["parse_errors"] += 1

    def _dispatch(self, data: bytes, exporter_ip: str):
        """Route packet to v5 or v9 parser based on version field."""
        if len(data) < 2:
            return
        version = struct.unpack("!H", data[:2])[0]
        try:
            if version == 5:
                self.stats["v5_packets"] += 1
                self._parse_v5(data, exporter_ip)
            elif version == 9:
                self.stats["v9_packets"] += 1
                self._parse_v9(data, exporter_ip)
            # Silently ignore other versions (v1, IPFIX/v10, etc.)
        except Exception as exc:
            self.stats["parse_errors"] += 1
            self.logger.log_error(None, f"Parse error ({exporter_ip}): {exc}", "netflow_parse")

    # ── NetFlow v5 parser ─────────────────────────────────────────────────────

    def _parse_v5(self, data: bytes, exporter_ip: str):
        if len(data) < _NF5_HDR_SIZE:
            return

        hdr = struct.unpack_from(_NF5_HDR_FMT, data, 0)
        count     = hdr[1]
        sys_uptime = hdr[2]        # milliseconds since boot
        unix_secs  = hdr[3]

        export_ts = datetime.fromtimestamp(unix_secs, tz=timezone.utc).isoformat()

        offset = _NF5_HDR_SIZE
        for _ in range(count):
            if offset + _NF5_REC_SIZE > len(data):
                break
            rec = struct.unpack_from(_NF5_REC_FMT, data, offset)
            offset += _NF5_REC_SIZE

            (srcaddr, dstaddr, _nexthop, _in, _out,
             pkts, octets, first_ms, last_ms,
             src_port, dst_port,
             _pad1, _tcp_flags, prot, _tos,
             _src_as, _dst_as, _src_mask, _dst_mask, _pad2) = rec

            duration_ms = (last_ms - first_ms) if last_ms >= first_ms else 0

            flow = {
                "timestamp":   export_ts,
                "exporter":    exporter_ip,
                "version":     5,
                "src_ip":      _ip(srcaddr),
                "dst_ip":      _ip(dstaddr),
                "src_port":    src_port,
                "dst_port":    dst_port,
                "protocol":    _proto_name(prot),
                "protocol_num": prot,
                "packets":     pkts,
                "bytes":       octets,
                "duration_ms": duration_ms,
            }
            self._store_flow(flow)

    # ── NetFlow v9 parser ─────────────────────────────────────────────────────

    def _parse_v9(self, data: bytes, exporter_ip: str):
        if len(data) < _NF9_HDR_SIZE:
            return

        hdr = struct.unpack_from(_NF9_HDR_FMT, data, 0)
        _version, _count, _uptime, unix_secs, _pkg_seq, source_id = hdr
        export_ts = datetime.fromtimestamp(unix_secs, tz=timezone.utc).isoformat()

        offset = _NF9_HDR_SIZE
        while offset + _NF9_FS_HDR_SIZE <= len(data):
            fs_id, fs_len = struct.unpack_from(_NF9_FS_HDR_FMT, data, offset)

            if fs_len < _NF9_FS_HDR_SIZE or offset + fs_len > len(data):
                break

            payload = data[offset + _NF9_FS_HDR_SIZE: offset + fs_len]

            if fs_id == 0:
                # Template flowset
                self._parse_v9_template(payload, exporter_ip, source_id)
            elif fs_id == 1:
                pass  # Options template — skip
            elif fs_id >= 256:
                # Data flowset — fs_id IS the template_id
                tpl_key = (exporter_ip, source_id, fs_id)
                template = self._v9_templates.get(tpl_key)
                if template:
                    self._parse_v9_data(payload, template, exporter_ip, export_ts)

            offset += fs_len
            # Align to 4-byte boundary
            if fs_len % 4:
                offset += 4 - (fs_len % 4)

    def _parse_v9_template(self, payload: bytes, exporter_ip: str, source_id: int):
        """Parse a v9 template flowset; register each template found."""
        offset = 0
        while offset + 4 <= len(payload):
            tpl_id, field_count = struct.unpack_from("!HH", payload, offset)
            offset += 4

            fields = []
            for _ in range(field_count):
                if offset + 4 > len(payload):
                    break
                ftype, flen = struct.unpack_from("!HH", payload, offset)
                offset += 4

                if ftype in _NF9_FIELDS:
                    fname, _ = _NF9_FIELDS[ftype]
                    fields.append((fname, ftype, flen))
                else:
                    fields.append((None, ftype, flen))  # unknown — skip bytes

            tpl_key = (exporter_ip, source_id, tpl_id)
            self._v9_templates[tpl_key] = fields

    def _parse_v9_data(self, payload: bytes, template: list,
                       exporter_ip: str, export_ts: str):
        """Decode data flowset records using the registered template."""
        # Calculate record size from template
        rec_size = sum(flen for _, _, flen in template)
        if rec_size == 0:
            return

        offset = 0
        while offset + rec_size <= len(payload):
            raw_values: Dict[str, int] = {}
            rec_offset = offset

            for fname, _ftype, flen in template:
                chunk = payload[rec_offset: rec_offset + flen]
                rec_offset += flen

                if fname is None:
                    continue  # skip unknown field

                if fname in ("src_addr", "dst_addr"):
                    raw_values[fname] = chunk  # keep as bytes for _ip()
                elif flen == 1:
                    raw_values[fname] = chunk[0] if chunk else 0
                elif flen == 2:
                    raw_values[fname] = struct.unpack("!H", chunk)[0] if len(chunk) == 2 else 0
                elif flen == 4:
                    raw_values[fname] = struct.unpack("!I", chunk)[0] if len(chunk) == 4 else 0
                else:
                    raw_values[fname] = int.from_bytes(chunk, "big")

            offset += rec_size

            # Skip padding records (all zeros)
            if not any(raw_values.values()):
                continue

            src_raw = raw_values.get("src_addr", b"\x00\x00\x00\x00")
            dst_raw = raw_values.get("dst_addr", b"\x00\x00\x00\x00")
            prot_num = raw_values.get("protocol", 0)

            first_ms = raw_values.get("first_sw", 0)
            last_ms  = raw_values.get("last_sw", 0)
            duration_ms = (last_ms - first_ms) if last_ms >= first_ms else 0

            flow = {
                "timestamp":    export_ts,
                "exporter":     exporter_ip,
                "version":      9,
                "src_ip":       _ip(src_raw) if isinstance(src_raw, bytes) else "0.0.0.0",
                "dst_ip":       _ip(dst_raw) if isinstance(dst_raw, bytes) else "0.0.0.0",
                "src_port":     raw_values.get("src_port", 0),
                "dst_port":     raw_values.get("dst_port", 0),
                "protocol":     _proto_name(prot_num),
                "protocol_num": prot_num,
                "packets":      raw_values.get("in_pkts",   raw_values.get("out_pkts",  0)),
                "bytes":        raw_values.get("in_bytes",  raw_values.get("out_bytes", 0)),
                "duration_ms":  duration_ms,
            }
            self._store_flow(flow)

    # ── Flow storage & queries ────────────────────────────────────────────────

    def _store_flow(self, flow: dict):
        with self._lock:
            self._flows.append(flow)
        self.stats["flows_decoded"] += 1

    def get_flows(self, limit: int = 500, exporter: Optional[str] = None) -> List[dict]:
        """Return the most recent flows, optionally filtered by exporter IP."""
        with self._lock:
            flows = list(self._flows)
        if exporter:
            flows = [f for f in flows if f["exporter"] == exporter]
        return flows[-limit:]

    def get_top_talkers(self, n: int = 10, by: str = "bytes") -> List[dict]:
        """
        Aggregate flows by source IP and return the top-N senders.
        `by` can be 'bytes' or 'packets'.
        """
        with self._lock:
            flows = list(self._flows)

        totals: Dict[str, Dict] = {}
        for f in flows:
            src = f["src_ip"]
            if src not in totals:
                totals[src] = {"src_ip": src, "bytes": 0, "packets": 0, "flows": 0}
            totals[src]["bytes"]   += f.get("bytes",   0)
            totals[src]["packets"] += f.get("packets", 0)
            totals[src]["flows"]   += 1

        ranked = sorted(totals.values(), key=lambda x: x[by], reverse=True)
        return ranked[:n]

    def get_top_conversations(self, n: int = 10) -> List[dict]:
        """Return top-N src↔dst pairs by bytes."""
        with self._lock:
            flows = list(self._flows)

        totals: Dict[Tuple, Dict] = {}
        for f in flows:
            key = (f["src_ip"], f["dst_ip"], f["protocol"])
            if key not in totals:
                totals[key] = {
                    "src_ip": f["src_ip"], "dst_ip": f["dst_ip"],
                    "protocol": f["protocol"],
                    "bytes": 0, "packets": 0, "flows": 0,
                }
            totals[key]["bytes"]   += f.get("bytes",   0)
            totals[key]["packets"] += f.get("packets", 0)
            totals[key]["flows"]   += 1

        ranked = sorted(totals.values(), key=lambda x: x["bytes"], reverse=True)
        return ranked[:n]

    def clear_flows(self):
        """Discard all buffered flows."""
        with self._lock:
            self._flows.clear()
        self.logger.log_event("netflow_cleared", None, "Flow buffer cleared", status="info")

    def get_stats(self) -> dict:
        """Return collector statistics."""
        with self._lock:
            buffered = len(self._flows)
        return {
            **self.stats,
            "buffered_flows": buffered,
            "running":        self.is_running,
            "listen_port":    self.port,
        }

    def export_flows_csv(self, filepath: str, limit: int = 10_000) -> Tuple[bool, str]:
        """Export buffered flows to a CSV file."""
        import csv
        from pathlib import Path

        flows = self.get_flows(limit=limit)
        if not flows:
            return False, "No flows to export"

        try:
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            fieldnames = ["timestamp", "exporter", "version", "src_ip", "dst_ip",
                          "src_port", "dst_port", "protocol", "packets", "bytes", "duration_ms"]
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(flows)
            return True, f"Exported {len(flows)} flows to {filepath}"
        except Exception as exc:
            return False, f"Export failed: {exc}"
