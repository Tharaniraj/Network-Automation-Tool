"""
Device Management Module
Handles device discovery, inventory, and connectivity
"""

import json
import socket
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
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
        self.devices = self._load_devices()
        self.logger = get_observability_manager()

    def _load_devices(self) -> Dict[str, Dict]:
        """Load devices from JSON file"""
        if self.data_file.exists():
            with open(self.data_file, 'r') as f:
                return json.load(f)
        return {}

    def _save_devices(self):
        """Save devices to JSON file"""
        with open(self.data_file, 'w') as f:
            json.dump(self.devices, f, indent=2)

    def add_device(self, hostname: str, ip_address: str, device_type: str,
                   username: str, password: str, port: int = 22,
                   snmp_community: str = "public", tags: List[str] = None) -> Tuple[bool, str]:
        """Add a new device to inventory"""
        try:
            if hostname in self.devices:
                return False, f"Device {hostname} already exists"
            
            if device_type not in self.DEVICE_TYPES:
                return False, f"Invalid device type: {device_type}"

            device = {
                "hostname": hostname,
                "ip_address": ip_address,
                "device_type": device_type,
                "vendor": self.DEVICE_TYPES[device_type]["vendor"],
                "os": self.DEVICE_TYPES[device_type]["os"],
                "username": username,
                "password": password,
                "port": port,
                "snmp_community": snmp_community,
                "tags": tags or [],
                "status": "unknown",
                "last_checked": None,
                "last_updated": datetime.now().isoformat(),
                "enabled": True
            }

            self.devices[hostname] = device
            self._save_devices()
            
            self.logger.log_event(
                event_type="device_added",
                device_name=hostname,
                description=f"Device added: {ip_address} ({device_type})",
                status="success"
            )
            
            return True, f"Device {hostname} added successfully"
        
        except Exception as e:
            self.logger.log_error(hostname, str(e), "add_device_error")
            return False, f"Error adding device: {str(e)}"

    def remove_device(self, hostname: str) -> Tuple[bool, str]:
        """Remove device from inventory"""
        try:
            if hostname not in self.devices:
                return False, f"Device {hostname} not found"
            
            del self.devices[hostname]
            self._save_devices()
            
            self.logger.log_event(
                event_type="device_removed",
                device_name=hostname,
                description=f"Device removed from inventory",
                status="success"
            )
            
            return True, f"Device {hostname} removed successfully"
        
        except Exception as e:
            self.logger.log_error(hostname, str(e), "remove_device_error")
            return False, f"Error removing device: {str(e)}"

    def update_device(self, hostname: str, **kwargs) -> Tuple[bool, str]:
        """Update device information"""
        try:
            if hostname not in self.devices:
                return False, f"Device {hostname} not found"
            
            # Validate updates
            valid_fields = {"username", "password", "port", "snmp_community", "tags", "enabled"}
            for key in kwargs:
                if key not in valid_fields:
                    return False, f"Cannot update field: {key}"
            
            self.devices[hostname].update(kwargs)
            self.devices[hostname]["last_updated"] = datetime.now().isoformat()
            self._save_devices()
            
            self.logger.log_event(
                event_type="device_updated",
                device_name=hostname,
                description=f"Device configuration updated",
                status="success",
                details=kwargs
            )
            
            return True, f"Device {hostname} updated successfully"
        
        except Exception as e:
            self.logger.log_error(hostname, str(e), "update_device_error")
            return False, f"Error updating device: {str(e)}"

    def get_device(self, hostname: str) -> Optional[Dict]:
        """Get device details"""
        return self.devices.get(hostname)

    def get_all_devices(self, filter_enabled: bool = True) -> List[Dict]:
        """Get all devices, optionally filtered"""
        devices = list(self.devices.values())
        if filter_enabled:
            devices = [d for d in devices if d.get("enabled", True)]
        return devices

    def get_devices_by_type(self, device_type: str) -> List[Dict]:
        """Get devices of specific type"""
        return [d for d in self.devices.values() if d.get("device_type") == device_type]

    def get_devices_by_vendor(self, vendor: str) -> List[Dict]:
        """Get devices by vendor"""
        return [d for d in self.devices.values() if d.get("vendor") == vendor]

    def get_devices_by_tag(self, tag: str) -> List[Dict]:
        """Get devices with specific tag"""
        return [d for d in self.devices.values() if tag in d.get("tags", [])]

    def discover_devices(self, network: str, username: str, password: str,
                        device_type: str) -> Tuple[List[Dict], List[str]]:
        """
        Discover devices in a network (IP range)
        Format: '192.168.1.0/24' or '192.168.1.1-10'
        """
        found_devices = []
        errors = []
        
        try:
            ips = self._parse_network_range(network)
            self.logger.log_event(
                event_type="discovery_started",
                device_name=None,
                description=f"Device discovery started for {network}",
                status="info"
            )
            
            for ip in ips:
                if self._check_connectivity(ip):
                    found_devices.append({
                        "ip": ip,
                        "device_type": device_type,
                        "username": username,
                        "hostname": f"device-{ip.replace('.', '-')}"
                    })
            
            self.logger.log_event(
                event_type="discovery_completed",
                device_name=None,
                description=f"Discovery complete: {len(found_devices)} devices found",
                status="success"
            )
            
        except Exception as e:
            errors.append(f"Discovery error: {str(e)}")
            self.logger.log_error(None, str(e), "discovery_error")
        
        return found_devices, errors

    @staticmethod
    def _parse_network_range(network: str) -> List[str]:
        """Parse network range (simple implementation)"""
        ips = []
        if '-' in network:
            # Format: 192.168.1.1-10
            parts = network.rsplit('.', 1)
            base = parts[0] + '.'
            start, end = parts[1].split('-')
            for i in range(int(start), int(end) + 1):
                ips.append(f"{base}{i}")
        else:
            # Format: 192.168.1.0/24 (simplified - just example IPs)
            base = network.rsplit('.', 1)[0] + '.'
            for i in range(1, 11):  # Example: check first 10 IPs
                ips.append(f"{base}{i}")
        return ips

    @staticmethod
    def _check_connectivity(ip: str, port: int = 22, timeout: int = 2) -> bool:
        """Check if device is reachable"""
        try:
            socket.create_connection((ip, port), timeout=timeout)
            return True
        except (socket.timeout, socket.error):
            return False

    def update_device_status(self, hostname: str, status: str) -> bool:
        """Update device status (online/offline/error)"""
        if hostname in self.devices:
            self.devices[hostname]["status"] = status
            self.devices[hostname]["last_checked"] = datetime.now().isoformat()
            self._save_devices()
            return True
        return False

    def get_inventory_stats(self) -> Dict:
        """Get inventory statistics"""
        devices = self.get_all_devices(filter_enabled=False)
        return {
            "total_devices": len(devices),
            "enabled_devices": len([d for d in devices if d.get("enabled", True)]),
            "online_devices": len([d for d in devices if d.get("status") == "online"]),
            "offline_devices": len([d for d in devices if d.get("status") == "offline"]),
            "cisco_devices": len(self.get_devices_by_vendor("Cisco")),
            "huawei_devices": len(self.get_devices_by_vendor("Huawei")),
            "device_types": list(set(d.get("device_type") for d in devices))
        }
