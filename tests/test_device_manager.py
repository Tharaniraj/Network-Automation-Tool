"""
Unit tests for modules/device_manager.py
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

try:
    from cryptography.fernet import Fernet
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

from modules.device_manager import DeviceManager


def _make_manager(tmp_path: str) -> DeviceManager:
    """Return a DeviceManager backed by a temp file with a no-op logger."""
    data_file = str(Path(tmp_path) / "devices.json")
    mgr = DeviceManager(data_file=data_file)
    # Stub out the logger so tests don't write to disk
    mgr.logger = MagicMock()
    return mgr


class TestAddDevice(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mgr = _make_manager(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_valid_device(self):
        ok, msg = self.mgr.add_device("r1", "192.168.1.1", "cisco_router", "admin", "secret")
        self.assertTrue(ok)
        self.assertIn("r1", self.mgr.devices)

    def test_add_duplicate_hostname(self):
        self.mgr.add_device("r1", "192.168.1.1", "cisco_router", "admin", "s")
        ok, msg = self.mgr.add_device("r1", "192.168.1.2", "cisco_router", "admin", "s")
        self.assertFalse(ok)
        self.assertIn("already exists", msg)

    def test_add_invalid_device_type(self):
        ok, msg = self.mgr.add_device("r1", "192.168.1.1", "juniper_router", "admin", "s")
        self.assertFalse(ok)
        self.assertIn("Invalid device type", msg)

    def test_add_invalid_ip(self):
        ok, msg = self.mgr.add_device("r1", "999.999.999.999", "cisco_router", "admin", "s")
        self.assertFalse(ok)
        self.assertIn("Invalid IP", msg)

    @unittest.skipUnless(CRYPTO_AVAILABLE, "cryptography library not installed")
    def test_password_is_stored_encrypted(self):
        """Raw password must not appear in the stored record."""
        self.mgr.add_device("r1", "10.0.0.1", "cisco_router", "admin", "supersecret")
        stored_pwd = self.mgr.devices["r1"]["password"]
        self.assertNotEqual(stored_pwd, "supersecret")

    @unittest.skipUnless(CRYPTO_AVAILABLE, "cryptography library not installed")
    def test_get_device_returns_decrypted_password(self):
        self.mgr.add_device("r1", "10.0.0.1", "cisco_router", "admin", "supersecret")
        device = self.mgr.get_device("r1")
        self.assertEqual(device["password"], "supersecret")

    def test_device_persisted_to_disk(self):
        self.mgr.add_device("r1", "10.0.0.1", "cisco_router", "admin", "s")
        with open(self.mgr.data_file) as f:
            on_disk = json.load(f)
        self.assertIn("r1", on_disk)


class TestRemoveDevice(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mgr = _make_manager(self.tmp.name)
        self.mgr.add_device("r1", "10.0.0.1", "cisco_router", "admin", "s")

    def tearDown(self):
        self.tmp.cleanup()

    def test_remove_existing(self):
        ok, msg = self.mgr.remove_device("r1")
        self.assertTrue(ok)
        self.assertNotIn("r1", self.mgr.devices)

    def test_remove_nonexistent(self):
        ok, msg = self.mgr.remove_device("ghost")
        self.assertFalse(ok)
        self.assertIn("not found", msg)


class TestUpdateDevice(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mgr = _make_manager(self.tmp.name)
        self.mgr.add_device("r1", "10.0.0.1", "cisco_router", "admin", "oldpass")

    def tearDown(self):
        self.tmp.cleanup()

    def test_update_username(self):
        ok, _ = self.mgr.update_device("r1", username="newadmin")
        self.assertTrue(ok)
        self.assertEqual(self.mgr.devices["r1"]["username"], "newadmin")

    @unittest.skipUnless(CRYPTO_AVAILABLE, "cryptography library not installed")
    def test_update_password_is_encrypted(self):
        self.mgr.update_device("r1", password="newpass")
        stored = self.mgr.devices["r1"]["password"]
        self.assertNotEqual(stored, "newpass")
        # But decrypting should give the new value
        self.assertEqual(self.mgr.get_device("r1")["password"], "newpass")

    def test_update_invalid_field(self):
        ok, msg = self.mgr.update_device("r1", ip_address="1.2.3.4")
        self.assertFalse(ok)
        self.assertIn("Cannot update field", msg)

    def test_update_nonexistent_device(self):
        ok, msg = self.mgr.update_device("ghost", username="x")
        self.assertFalse(ok)


class TestNetworkRangeParsing(unittest.TestCase):

    def test_cidr_24(self):
        ips = DeviceManager._parse_network_range("192.168.1.0/24")
        self.assertEqual(len(ips), 254)
        self.assertIn("192.168.1.1", ips)
        self.assertIn("192.168.1.254", ips)
        self.assertNotIn("192.168.1.0", ips)    # network address excluded
        self.assertNotIn("192.168.1.255", ips)  # broadcast excluded

    def test_cidr_30(self):
        ips = DeviceManager._parse_network_range("10.0.0.0/30")
        self.assertEqual(len(ips), 2)
        self.assertIn("10.0.0.1", ips)
        self.assertIn("10.0.0.2", ips)

    def test_hyphen_range(self):
        ips = DeviceManager._parse_network_range("192.168.1.1-5")
        self.assertEqual(ips, ["192.168.1.1", "192.168.1.2", "192.168.1.3",
                                "192.168.1.4", "192.168.1.5"])

    def test_invalid_cidr_raises(self):
        with self.assertRaises(ValueError):
            DeviceManager._parse_network_range("not_an_ip")

    def test_invalid_range_raises(self):
        with self.assertRaises(ValueError):
            DeviceManager._parse_network_range("192.168.1.10-5")  # start > end


class TestInventoryStats(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mgr = _make_manager(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_empty_inventory(self):
        stats = self.mgr.get_inventory_stats()
        self.assertEqual(stats["total_devices"], 0)

    def test_counts_vendors(self):
        self.mgr.add_device("r1", "10.0.0.1", "cisco_router", "a", "b")
        self.mgr.add_device("r2", "10.0.0.2", "huawei_router", "a", "b")
        stats = self.mgr.get_inventory_stats()
        self.assertEqual(stats["total_devices"], 2)
        self.assertEqual(stats["cisco_devices"], 1)
        self.assertEqual(stats["huawei_devices"], 1)


if __name__ == "__main__":
    unittest.main()
