"""
Device Management Module
Handles device discovery, inventory, and connectivity
"""

import ipaddress
import json
import socket
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from .crypto import get_vault
from .logger import get_observability_manager


class DeviceManager:
    """Manages network device inventory and discovery"""

    DEVICE_TYPES = {
        "cisco_router": {"os": "Cisco IOS/IOS-XE", "vendor": "Cisco"},
        "cisco_switch": {"os": "Cisco IOS/IOS-XE", "vendor": "Cisco"},
        "huawei_router": {"os": "Huawei VRP", "vendor": "Huawei"},
        "huawei_switch": {"os": "Huawei VRP", "vendor": "Huawei"},
    }

    def __init__(self, data_file: str = "data/devices.json"):
        self.data_file = Path(data_file)
        self.data_file.parent.mkdir(exist_ok=True)
        self._vault = get_vault()
        self.logger = get_observability_manager()
        self.devices = self._load_devices()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _load_devices(self) -> Dict[str, Dict]:
        """Load devices from JSON file."""
        if self.data_file.exists():
            with open(self.data_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_devices(self):
        """Persist device inventory to disk."""
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.devices, f, indent=2)

    # ------------------------------------------------------------------
    # Credential helpers
    # ------------------------------------------------------------------

    def _encrypt_password(self, password: str) -> str:
        return self._vault.encrypt(password)

    def _decrypt_password(self, stored: str) -> str:
        return self._vault.decrypt(stored)

    def _device_with_clear_password(self, device: Dict) -> Dict:
        """Return a copy of the device record with the password decrypted."""
        d = dict(device)
        d["password"] = self._decrypt_password(d.get("password", ""))
        return d

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add_device(self, hostname: str, ip_address: str, device_type: str,
                   username: str, password: str, port: int = 22,
                   snmp_community: str = "public",
                   tags: List[str] = None) -> Tuple[bool, str]:
        """Add a new device to inventory (password is stored encrypted)."""
        try:
            if hostname in self.devices:
                return False, f"Device {hostname} already exists"

            if device_type not in self.DEVICE_TYPES:
                return False, f"Invalid device type: {device_type}"

            # Validate IP address
            try:
                ipaddress.ip_address(ip_address)
            except ValueError:
                return False, f"Invalid IP address: {ip_address}"

            device = {
                "hostname": hostname,
                "ip_address": ip_address,
                "device_type": device_type,
                "vendor": self.DEVICE_TYPES[device_type]["vendor"],
                "os": self.DEVICE_TYPES[device_type]["os"],
                "username": username,
                "password": self._encrypt_password(password),
                "port": port,
                "snmp_community": snmp_community,
                "tags": tags or [],
                "status": "unknown",
                "last_checked": None,
                "last_updated": datetime.now().isoformat(),
                "enabled": True,
            }

            self.devices[hostname] = device
            self._save_devices()

            self.logger.log_event(
                event_type="device_added",
                device_name=hostname,
                description=f"Device added: {ip_address} ({device_type})",
                status="success",
            )

            return True, f"Device {hostname} added successfully"

        except Exception as exc:
            self.logger.log_error(hostname, str(exc), "add_device_error")
            return False, f"Error adding device: {exc}"

    def remove_device(self, hostname: str) -> Tuple[bool, str]:
        """Remove device from inventory."""
        try:
            if hostname not in self.devices:
                return False, f"Device {hostname} not found"

            del self.devices[hostname]
            self._save_devices()

            self.logger.log_event(
                event_type="device_removed",
                device_name=hostname,
                description="Device removed from inventory",
                status="success",
            )

            return True, f"Device {hostname} removed successfully"

        except Exception as exc:
            self.logger.log_error(hostname, str(exc), "remove_device_error")
            return False, f"Error removing device: {exc}"

    def update_device(self, hostname: str, **kwargs) -> Tuple[bool, str]:
        """Update device information. Passwords supplied here are re-encrypted."""
        try:
            if hostname not in self.devices:
                return False, f"Device {hostname} not found"

            valid_fields = {"username", "password", "port", "snmp_community", "tags", "enabled"}
            for key in kwargs:
                if key not in valid_fields:
                    return False, f"Cannot update field: {key}"

            if "password" in kwargs:
                kwargs["password"] = self._encrypt_password(kwargs["password"])

            self.devices[hostname].update(kwargs)
            self.devices[hostname]["last_updated"] = datetime.now().isoformat()
            self._save_devices()

            log_kwargs = {k: v for k, v in kwargs.items() if k != "password"}
            self.logger.log_event(
                event_type="device_updated",
                device_name=hostname,
                description="Device configuration updated",
                status="success",
                details=log_kwargs,
            )

            return True, f"Device {hostname} updated successfully"

        except Exception as exc:
            self.logger.log_error(hostname, str(exc), "update_device_error")
            return False, f"Error updating device: {exc}"

    def get_device(self, hostname: str) -> Optional[Dict]:
        """Get device details with the password decrypted."""
        device = self.devices.get(hostname)
        if device is None:
            return None
        return self._device_with_clear_password(device)

    def get_all_devices(self, filter_enabled: bool = True) -> List[Dict]:
        """Get all devices (passwords decrypted), optionally filtered."""
        devices = [self._device_with_clear_password(d) for d in self.devices.values()]
        if filter_enabled:
            devices = [d for d in devices if d.get("enabled", True)]
        return devices

    def get_devices_by_type(self, device_type: str) -> List[Dict]:
        return [self._device_with_clear_password(d)
                for d in self.devices.values() if d.get("device_type") == device_type]

    def get_devices_by_vendor(self, vendor: str) -> List[Dict]:
        return [self._device_with_clear_password(d)
                for d in self.devices.values() if d.get("vendor") == vendor]

    def get_devices_by_tag(self, tag: str) -> List[Dict]:
        return [self._device_with_clear_password(d)
                for d in self.devices.values() if tag in d.get("tags", [])]

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover_devices(self, network: str, username: str, password: str,
                         device_type: str) -> Tuple[List[Dict], List[str]]:
        """
        Discover reachable devices in a network range.
        Accepts CIDR notation (192.168.1.0/24) or range (192.168.1.1-10).
        """
        found_devices: List[Dict] = []
        errors: List[str] = []

        try:
            ips = self._parse_network_range(network)
            self.logger.log_event(
                event_type="discovery_started",
                device_name=None,
                description=f"Device discovery started for {network} ({len(ips)} hosts)",
                status="info",
            )

            for ip in ips:
                if self._check_connectivity(ip):
                    found_devices.append({
                        "ip": ip,
                        "device_type": device_type,
                        "username": username,
                        "hostname": f"device-{ip.replace('.', '-')}",
                    })

            self.logger.log_event(
                event_type="discovery_completed",
                device_name=None,
                description=f"Discovery complete: {len(found_devices)} devices found",
                status="success",
            )

        except Exception as exc:
            errors.append(f"Discovery error: {exc}")
            self.logger.log_error(None, str(exc), "discovery_error")

        return found_devices, errors

    @staticmethod
    def _parse_network_range(network: str) -> List[str]:
        """
        Parse a network range into a list of IP address strings.

        Supported formats:
          CIDR  — 192.168.1.0/24  (all host addresses in the subnet)
          Range — 192.168.1.1-10  (192.168.1.1 through 192.168.1.10)
        """
        network = network.strip()

        # Hyphen range: 192.168.1.1-10
        if "-" in network and "/" not in network:
            base, last_octet_range = network.rsplit(".", 1)
            start_s, end_s = last_octet_range.split("-", 1)
            start, end = int(start_s), int(end_s)
            if not (0 <= start <= 255 and 0 <= end <= 255 and start <= end):
                raise ValueError(f"Invalid IP range: {network}")
            return [f"{base}.{i}" for i in range(start, end + 1)]

        # CIDR notation
        net = ipaddress.ip_network(network, strict=False)
        # Skip network and broadcast addresses for /24 and smaller
        hosts = list(net.hosts()) if net.prefixlen < 32 else [net.network_address]
        return [str(ip) for ip in hosts]

    @staticmethod
    def _check_connectivity(ip: str, port: int = 22, timeout: int = 2) -> bool:
        """Check if a device is reachable on the given TCP port."""
        try:
            with socket.create_connection((ip, port), timeout=timeout):
                return True
        except (socket.timeout, socket.error):
            return False

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def update_device_status(self, hostname: str, status: str) -> bool:
        """Update device status (online/offline/error)."""
        if hostname in self.devices:
            self.devices[hostname]["status"] = status
            self.devices[hostname]["last_checked"] = datetime.now().isoformat()
            self._save_devices()
            return True
        return False

    def get_inventory_stats(self) -> Dict:
        """Get inventory statistics."""
        devices = self.get_all_devices(filter_enabled=False)
        return {
            "total_devices": len(devices),
            "enabled_devices": len([d for d in devices if d.get("enabled", True)]),
            "online_devices": len([d for d in devices if d.get("status") == "online"]),
            "offline_devices": len([d for d in devices if d.get("status") == "offline"]),
            "cisco_devices": len(self.get_devices_by_vendor("Cisco")),
            "huawei_devices": len(self.get_devices_by_vendor("Huawei")),
            "device_types": list(set(d.get("device_type") for d in devices)),
        }
