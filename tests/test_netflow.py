"""
Unit tests for modules/netflow.py

Tests cover:
  - NetFlow v5 binary packet parsing
  - NetFlow v9 template + data flowset parsing
  - Flow storage, retrieval, and circular-buffer cap
  - Top talkers / top conversations aggregation
  - CSV export
  - Collector start/stop lifecycle (no real socket — mocked)
"""

import socket
import struct
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from modules.netflow import (
    NetFlowCollector,
    _NF5_HDR_FMT, _NF5_HDR_SIZE,
    _NF5_REC_FMT, _NF5_REC_SIZE,
    _NF9_HDR_FMT, _NF9_HDR_SIZE,
    _NF9_FS_HDR_FMT,
    _MAX_FLOWS,
)


# ── Packet builders ────────────────────────────────────────────────────────────

def _make_v5_packet(flows: list) -> bytes:
    """
    Build a minimal NetFlow v5 UDP payload.
    flows = list of (src_ip, dst_ip, src_port, dst_port, proto, pkts, octets)
    """
    import time as _time
    unix_secs = int(_time.time())
    header = struct.pack(_NF5_HDR_FMT,
        5, len(flows), 60000, unix_secs, 0, 0, 0, 0, 0)

    records = b""
    for src, dst, sp, dp, proto, pkts, octets in flows:
        records += struct.pack(_NF5_REC_FMT,
            socket.inet_aton(src),   # srcaddr
            socket.inet_aton(dst),   # dstaddr
            socket.inet_aton("0.0.0.0"),  # nexthop
            0, 0,                    # input, output
            pkts, octets,            # dPkts, dOctets
            1000, 2000,              # first_ms, last_ms  → duration = 1000 ms
            sp, dp,                  # srcport, dstport
            0, 0,                    # pad1, tcp_flags
            proto, 0,                # prot, tos
            0, 0,                    # src_as, dst_as
            0, 0, 0,                 # src_mask, dst_mask, pad2
        )
    return header + records


def _make_v9_packet_with_template(
    template_id: int,
    src_ip: str, dst_ip: str,
    src_port: int, dst_port: int,
    proto: int, pkts: int, octets: int,
) -> bytes:
    """
    Build a NetFlow v9 packet containing one template flowset and one data flowset.
    Fields used: src_addr(8), dst_addr(12), src_port(7), dst_port(11),
                 protocol(4), in_pkts(2), in_bytes(1)
    """
    import time as _time
    unix_secs = int(_time.time())

    # Field definitions: (field_type, field_length)
    field_defs = [(8, 4), (12, 4), (7, 2), (11, 2), (4, 1), (2, 4), (1, 4)]
    field_count = len(field_defs)

    # Template flowset body
    tpl_body = struct.pack("!HH", template_id, field_count)
    for ftype, flen in field_defs:
        tpl_body += struct.pack("!HH", ftype, flen)

    tpl_fs_len = 4 + len(tpl_body)  # flowset header + body
    tpl_flowset = struct.pack("!HH", 0, tpl_fs_len) + tpl_body

    # Data flowset body (one record)
    rec_size = sum(flen for _, flen in field_defs)
    data_body = (
        socket.inet_aton(src_ip) +    # src_addr  (4)
        socket.inet_aton(dst_ip) +    # dst_addr  (4)
        struct.pack("!H", src_port) + # src_port  (2)
        struct.pack("!H", dst_port) + # dst_port  (2)
        struct.pack("!B", proto) +    # protocol  (1)
        struct.pack("!I", pkts) +     # in_pkts   (4)
        struct.pack("!I", octets)     # in_bytes  (4)
    )
    data_fs_len = 4 + len(data_body)
    data_flowset = struct.pack("!HH", template_id, data_fs_len) + data_body

    flowset_count = 2
    header = struct.pack(_NF9_HDR_FMT, 9, flowset_count, 60000, unix_secs, 1, 0)
    return header + tpl_flowset + data_flowset


# ── Helpers ───────────────────────────────────────────────────────────────────

def _collector() -> NetFlowCollector:
    c = NetFlowCollector()
    c.logger = MagicMock()
    return c


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestNetFlowV5Parsing(unittest.TestCase):

    def setUp(self):
        self.c = _collector()

    def test_single_flow_parsed(self):
        pkt = _make_v5_packet([("10.0.0.1", "10.0.0.2", 1234, 80, 6, 100, 5000)])
        self.c._dispatch(pkt, "192.168.1.1")
        flows = self.c.get_flows()
        self.assertEqual(len(flows), 1)
        f = flows[0]
        self.assertEqual(f["src_ip"],   "10.0.0.1")
        self.assertEqual(f["dst_ip"],   "10.0.0.2")
        self.assertEqual(f["src_port"], 1234)
        self.assertEqual(f["dst_port"], 80)
        self.assertEqual(f["protocol"], "TCP")
        self.assertEqual(f["packets"],  100)
        self.assertEqual(f["bytes"],    5000)
        self.assertEqual(f["version"],  5)

    def test_multiple_flows_in_one_packet(self):
        flows_data = [
            ("10.0.0.1", "8.8.8.8",  5000, 53,  17, 1, 60),
            ("10.0.0.2", "8.8.4.4",  6000, 443,  6, 20, 3000),
            ("10.0.0.3", "10.0.0.1", 7000, 8080, 6, 5,  400),
        ]
        pkt = _make_v5_packet(flows_data)
        self.c._dispatch(pkt, "192.168.1.1")
        self.assertEqual(len(self.c.get_flows()), 3)

    def test_udp_protocol_name(self):
        pkt = _make_v5_packet([("1.1.1.1", "2.2.2.2", 5353, 53, 17, 1, 64)])
        self.c._dispatch(pkt, "192.168.1.1")
        self.assertEqual(self.c.get_flows()[0]["protocol"], "UDP")

    def test_icmp_protocol_name(self):
        pkt = _make_v5_packet([("1.1.1.1", "2.2.2.2", 0, 0, 1, 1, 28)])
        self.c._dispatch(pkt, "192.168.1.1")
        self.assertEqual(self.c.get_flows()[0]["protocol"], "ICMP")

    def test_exporter_ip_recorded(self):
        pkt = _make_v5_packet([("1.1.1.1", "2.2.2.2", 80, 80, 6, 1, 64)])
        self.c._dispatch(pkt, "172.16.0.1")
        self.assertEqual(self.c.get_flows()[0]["exporter"], "172.16.0.1")

    def test_duration_computed(self):
        pkt = _make_v5_packet([("1.1.1.1", "2.2.2.2", 80, 80, 6, 10, 1000)])
        self.c._dispatch(pkt, "10.0.0.1")
        # first_ms=1000, last_ms=2000 → duration=1000
        self.assertEqual(self.c.get_flows()[0]["duration_ms"], 1000)

    def test_short_packet_ignored(self):
        self.c._dispatch(b"\x00\x05", "10.0.0.1")  # version only, no header
        self.assertEqual(len(self.c.get_flows()), 0)

    def test_unknown_version_ignored(self):
        pkt = struct.pack("!H", 7) + b"\x00" * 100
        self.c._dispatch(pkt, "10.0.0.1")
        self.assertEqual(len(self.c.get_flows()), 0)


class TestNetFlowV9Parsing(unittest.TestCase):

    def setUp(self):
        self.c = _collector()

    def test_v9_flow_parsed(self):
        pkt = _make_v9_packet_with_template(
            256, "10.0.0.5", "10.0.0.6", 4444, 443, 6, 50, 7500
        )
        self.c._dispatch(pkt, "192.168.1.2")
        flows = self.c.get_flows()
        self.assertEqual(len(flows), 1)
        f = flows[0]
        self.assertEqual(f["src_ip"],   "10.0.0.5")
        self.assertEqual(f["dst_ip"],   "10.0.0.6")
        self.assertEqual(f["src_port"], 4444)
        self.assertEqual(f["dst_port"], 443)
        self.assertEqual(f["protocol"], "TCP")
        self.assertEqual(f["packets"],  50)
        self.assertEqual(f["bytes"],    7500)
        self.assertEqual(f["version"],  9)

    def test_v9_data_without_template_not_stored(self):
        """A data flowset with no matching template should be silently dropped."""
        import time as _t
        # Craft a data flowset only (no template flowset) with template_id=512
        data_body = b"\x00" * 21  # arbitrary
        data_flowset = struct.pack("!HH", 512, 4 + len(data_body)) + data_body
        header = struct.pack(_NF9_HDR_FMT, 9, 1, 60000, int(_t.time()), 1, 0)
        pkt = header + data_flowset
        self.c._dispatch(pkt, "10.0.0.1")
        self.assertEqual(len(self.c.get_flows()), 0)

    def test_v9_template_registered(self):
        pkt = _make_v9_packet_with_template(
            300, "1.2.3.4", "5.6.7.8", 1024, 80, 6, 5, 500
        )
        self.c._dispatch(pkt, "10.0.0.1")
        key = ("10.0.0.1", 0, 300)
        self.assertIn(key, self.c._v9_templates)


class TestFlowStorageAndQueries(unittest.TestCase):

    def setUp(self):
        self.c = _collector()

    def _add_flows(self, n: int, src_prefix="10.0.0."):
        for i in range(n):
            pkt = _make_v5_packet(
                [(f"{src_prefix}{i % 254 + 1}", "8.8.8.8", 1000+i, 80, 6, i+1, (i+1)*100)]
            )
            self.c._dispatch(pkt, "192.168.1.1")

    def test_get_flows_limit(self):
        self._add_flows(100)
        self.assertEqual(len(self.c.get_flows(limit=10)), 10)

    def test_get_flows_exporter_filter(self):
        pkt = _make_v5_packet([("10.0.0.1", "10.0.0.2", 80, 80, 6, 1, 64)])
        self.c._dispatch(pkt, "192.168.1.1")
        self.c._dispatch(pkt, "192.168.1.2")
        self.assertEqual(len(self.c.get_flows(exporter="192.168.1.1")), 1)

    def test_clear_flows(self):
        self._add_flows(5)
        self.c.clear_flows()
        self.assertEqual(len(self.c.get_flows()), 0)

    def test_buffer_cap_enforced(self):
        """Adding more than _MAX_FLOWS should not exceed the cap."""
        for i in range(_MAX_FLOWS + 50):
            pkt = _make_v5_packet([("10.0.0.1", "10.0.0.2", i, 80, 6, 1, 64)])
            self.c._dispatch(pkt, "10.0.0.1")
        self.assertLessEqual(len(self.c._flows), _MAX_FLOWS)

    def test_top_talkers(self):
        # src 10.0.0.1 sends 1000 bytes, 10.0.0.2 sends 200 bytes
        for _ in range(5):
            pkt = _make_v5_packet([("10.0.0.1", "8.8.8.8", 1000, 80, 6, 1, 200)])
            self.c._dispatch(pkt, "10.0.0.1")
        pkt = _make_v5_packet([("10.0.0.2", "8.8.8.8", 2000, 80, 6, 1, 200)])
        self.c._dispatch(pkt, "10.0.0.1")

        talkers = self.c.get_top_talkers(n=2)
        self.assertEqual(talkers[0]["src_ip"], "10.0.0.1")
        self.assertGreater(talkers[0]["bytes"], talkers[1]["bytes"])

    def test_top_conversations(self):
        pkt = _make_v5_packet([("10.0.0.1", "10.0.0.2", 1000, 80, 6, 10, 1500)])
        for _ in range(3):
            self.c._dispatch(pkt, "10.0.0.1")

        convs = self.c.get_top_conversations()
        self.assertEqual(len(convs), 1)
        self.assertEqual(convs[0]["src_ip"], "10.0.0.1")
        self.assertEqual(convs[0]["dst_ip"], "10.0.0.2")
        self.assertEqual(convs[0]["flows"],  3)

    def test_stats_updated(self):
        pkt = _make_v5_packet([("1.1.1.1", "2.2.2.2", 80, 80, 6, 1, 64)])
        self.c._dispatch(pkt, "10.0.0.1")
        stats = self.c.get_stats()
        self.assertEqual(stats["v5_packets"],    1)
        self.assertEqual(stats["flows_decoded"], 1)
        self.assertEqual(stats["buffered_flows"], 1)


class TestCSVExport(unittest.TestCase):

    def setUp(self):
        self.c = _collector()
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_export_creates_file(self):
        pkt = _make_v5_packet([("10.0.0.1", "10.0.0.2", 80, 443, 6, 10, 1500)])
        self.c._dispatch(pkt, "10.0.0.1")
        path = str(Path(self.tmp.name) / "flows.csv")
        ok, msg = self.c.export_flows_csv(path)
        self.assertTrue(ok)
        self.assertTrue(Path(path).exists())

    def test_export_has_header_and_row(self):
        import csv
        pkt = _make_v5_packet([("10.0.0.1", "10.0.0.2", 80, 443, 6, 10, 1500)])
        self.c._dispatch(pkt, "10.0.0.1")
        path = str(Path(self.tmp.name) / "flows.csv")
        self.c.export_flows_csv(path)
        with open(path) as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 1)
        self.assertIn("src_ip", rows[0])

    def test_export_empty_buffer_returns_false(self):
        path = str(Path(self.tmp.name) / "empty.csv")
        ok, msg = self.c.export_flows_csv(path)
        self.assertFalse(ok)


class TestCollectorLifecycle(unittest.TestCase):
    """Tests that don't need a real socket (mock recvfrom)."""

    def test_start_stop(self):
        c = _collector()
        with patch.object(c, "_sock", MagicMock()):
            with patch("socket.socket") as mock_sock_cls:
                mock_sock = MagicMock()
                mock_sock_cls.return_value = mock_sock
                mock_sock.recvfrom.side_effect = socket.timeout

                ok, msg = c.start()
                self.assertTrue(ok)
                self.assertTrue(c.is_running)

                ok2, msg2 = c.stop()
                self.assertTrue(ok2)
                time.sleep(0.1)
                self.assertFalse(c.is_running)

    def test_double_start_returns_false(self):
        c = _collector()
        with patch("socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock_cls.return_value = mock_sock
            mock_sock.recvfrom.side_effect = socket.timeout
            c.start()
            ok, msg = c.start()
            self.assertFalse(ok)
            self.assertIn("already running", msg)
            c.stop()

    def test_stop_when_not_running_returns_false(self):
        c = _collector()
        ok, _ = c.stop()
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
