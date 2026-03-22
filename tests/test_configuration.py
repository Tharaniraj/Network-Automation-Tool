"""
Unit tests for modules/configuration.py
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from modules.configuration import ConfigurationManager


def _make_manager(tmp_path: str) -> ConfigurationManager:
    mgr = ConfigurationManager(
        config_dir=str(Path(tmp_path) / "configs"),
        backup_dir=str(Path(tmp_path) / "backups"),
    )
    mgr.logger = MagicMock()
    return mgr


SAMPLE_CONFIG = "hostname router1\nip ssh version 2\nntp server 10.0.0.1\n"
SAMPLE_CONFIG_V2 = "hostname router1\nip ssh version 2\nntp server 10.0.0.2\nbanner motd #Authorized#\n"


class TestBackupRestore(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mgr = _make_manager(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_backup_creates_file(self):
        ok, msg = self.mgr.backup_configuration("r1", SAMPLE_CONFIG)
        self.assertTrue(ok)
        backup_files = list(Path(self.tmp.name, "backups").glob("r1_*.config"))
        self.assertEqual(len(backup_files), 1)

    def test_backup_indexed(self):
        self.mgr.backup_configuration("r1", SAMPLE_CONFIG)
        backups = self.mgr.get_device_backups("r1")
        self.assertEqual(len(backups), 1)

    def test_restore_returns_content(self):
        self.mgr.backup_configuration("r1", SAMPLE_CONFIG)
        backup_name = self.mgr.get_device_backups("r1")[0]["name"]
        ok, msg, content = self.mgr.restore_configuration("r1", backup_name)
        self.assertTrue(ok)
        self.assertEqual(content, SAMPLE_CONFIG)

    def test_restore_missing_backup(self):
        ok, msg, content = self.mgr.restore_configuration("r1", "nonexistent.config")
        self.assertFalse(ok)
        self.assertEqual(content, "")

    def test_multiple_backups_tracked(self):
        self.mgr.backup_configuration("r1", SAMPLE_CONFIG)
        self.mgr.backup_configuration("r1", SAMPLE_CONFIG_V2)
        self.assertEqual(len(self.mgr.get_device_backups("r1")), 2)

    def test_delete_backup(self):
        self.mgr.backup_configuration("r1", SAMPLE_CONFIG)
        name = self.mgr.get_device_backups("r1")[0]["name"]
        ok, _ = self.mgr.delete_backup("r1", name)
        self.assertTrue(ok)
        self.assertEqual(len(self.mgr.get_device_backups("r1")), 0)


class TestSaveGetConfiguration(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mgr = _make_manager(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_and_retrieve(self):
        self.mgr.save_configuration("r1", SAMPLE_CONFIG)
        retrieved = self.mgr.get_configuration("r1")
        self.assertEqual(retrieved, SAMPLE_CONFIG)

    def test_get_nonexistent_returns_none(self):
        result = self.mgr.get_configuration("ghost")
        self.assertIsNone(result)


class TestCompareConfigurations(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mgr = _make_manager(self.tmp.name)
        self.mgr.backup_configuration("r1", SAMPLE_CONFIG)
        self.mgr.backup_configuration("r1", SAMPLE_CONFIG_V2)
        backups = self.mgr.get_device_backups("r1")
        self.backup_a = backups[0]["name"]
        self.backup_b = backups[1]["name"]

    def tearDown(self):
        self.tmp.cleanup()

    def test_compare_returns_diff(self):
        ok, msg, diff = self.mgr.compare_configurations("r1", self.backup_a, self.backup_b)
        self.assertTrue(ok)
        self.assertIn("unified_diff", diff)
        self.assertIn("added", diff)
        self.assertIn("removed", diff)

    def test_compare_detects_added_lines(self):
        _, _, diff = self.mgr.compare_configurations("r1", self.backup_a, self.backup_b)
        added = " ".join(diff["added"])
        self.assertIn("banner", added)

    def test_compare_detects_removed_lines(self):
        _, _, diff = self.mgr.compare_configurations("r1", self.backup_a, self.backup_b)
        # ntp server changed from 10.0.0.1 to 10.0.0.2 — old line is "removed"
        removed = " ".join(diff["removed"])
        self.assertIn("10.0.0.1", removed)

    def test_compare_identical_configs(self):
        self.mgr.backup_configuration("r1", SAMPLE_CONFIG, config_type="dup")
        backups = self.mgr.get_device_backups("r1")
        name_a = backups[0]["name"]
        name_c = backups[-1]["name"]
        ok, _, diff = self.mgr.compare_configurations("r1", name_a, name_c)
        self.assertTrue(ok)
        self.assertEqual(diff["added"], [])
        self.assertEqual(diff["removed"], [])

    def test_compare_missing_backup(self):
        ok, msg, _ = self.mgr.compare_configurations("r1", "missing.config", self.backup_b)
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
