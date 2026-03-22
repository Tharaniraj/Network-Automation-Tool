"""
Unit tests for modules/config_wizard.py
"""

import unittest
from modules.config_wizard import (
    # validators
    _vlan_id, _vlan_list, _hostname, _ip, _port, _community, _admin_distance,
    # tasks
    BackupTask, CreateVlanTask, DeleteVlanTask, AccessPortTask, TrunkPortTask,
    HostnameTask, PortDescriptionTask, InterfaceShutdownTask, BannerTask,
    SshEnableTask, LdapTask, NtpTask, SnmpTask, StaticRouteTask,
    # registry
    get_all_tasks, get_tasks_by_category, get_task_by_name,
)


# ── Validator tests ────────────────────────────────────────────────────────────

class TestValidators(unittest.TestCase):

    # _vlan_id
    def test_vlan_id_valid(self):
        self.assertIsNone(_vlan_id("1"))
        self.assertIsNone(_vlan_id("100"))
        self.assertIsNone(_vlan_id("4094"))

    def test_vlan_id_out_of_range(self):
        self.assertIsNotNone(_vlan_id("0"))
        self.assertIsNotNone(_vlan_id("4095"))

    def test_vlan_id_non_numeric(self):
        self.assertIsNotNone(_vlan_id("abc"))

    # _vlan_list
    def test_vlan_list_valid_single(self):
        self.assertIsNone(_vlan_list("10"))

    def test_vlan_list_valid_csv(self):
        self.assertIsNone(_vlan_list("10,20,30"))

    def test_vlan_list_valid_range(self):
        self.assertIsNone(_vlan_list("10-20"))

    def test_vlan_list_all(self):
        self.assertIsNone(_vlan_list("all"))

    def test_vlan_list_invalid_range(self):
        self.assertIsNotNone(_vlan_list("50-20"))   # start > end

    def test_vlan_list_non_numeric(self):
        self.assertIsNotNone(_vlan_list("abc"))

    # _hostname
    def test_hostname_valid(self):
        self.assertIsNone(_hostname("router1"))
        self.assertIsNone(_hostname("SW-Core-01"))

    def test_hostname_invalid_start(self):
        self.assertIsNotNone(_hostname("-router"))

    def test_hostname_too_long(self):
        self.assertIsNotNone(_hostname("a" * 64))

    # _ip
    def test_ip_valid(self):
        self.assertIsNone(_ip("192.168.1.1"))
        self.assertIsNone(_ip("10.0.0.1"))

    def test_ip_invalid(self):
        self.assertIsNotNone(_ip("999.999.999.999"))
        self.assertIsNotNone(_ip("not-an-ip"))

    # _port
    def test_port_valid(self):
        self.assertIsNone(_port("80"))
        self.assertIsNone(_port("65535"))

    def test_port_zero(self):
        self.assertIsNotNone(_port("0"))

    def test_port_too_high(self):
        self.assertIsNotNone(_port("65536"))

    # _community
    def test_community_valid(self):
        self.assertIsNone(_community("public"))
        self.assertIsNone(_community("My_SNMPv2c"))

    def test_community_invalid_chars(self):
        self.assertIsNotNone(_community("bad community"))

    def test_community_too_long(self):
        self.assertIsNotNone(_community("a" * 33))

    # _admin_distance
    def test_admin_distance_valid(self):
        self.assertIsNone(_admin_distance("1"))
        self.assertIsNone(_admin_distance("255"))

    def test_admin_distance_zero(self):
        self.assertIsNotNone(_admin_distance("0"))

    def test_admin_distance_too_high(self):
        self.assertIsNotNone(_admin_distance("256"))


# ── Registry tests ─────────────────────────────────────────────────────────────

class TestRegistry(unittest.TestCase):

    def test_get_all_tasks_returns_list(self):
        tasks = get_all_tasks()
        self.assertIsInstance(tasks, list)
        self.assertGreater(len(tasks), 0)

    def test_get_task_by_name_found(self):
        task = get_task_by_name("Create VLAN")
        self.assertIsNotNone(task)
        self.assertEqual(task.name, "Create VLAN")

    def test_get_task_by_name_not_found(self):
        self.assertIsNone(get_task_by_name("NonExistentTask"))

    def test_get_tasks_by_category_groups_correctly(self):
        cats = get_tasks_by_category()
        self.assertIn("VLAN", cats)
        self.assertIn("Basic Config", cats)
        self.assertIn("Security", cats)
        self.assertIn("Monitoring", cats)
        self.assertIn("Routing", cats)
        self.assertIn("Maintenance", cats)

    def test_all_tasks_have_name_and_category(self):
        for task in get_all_tasks():
            self.assertTrue(task.name, f"Task missing name: {task!r}")
            self.assertTrue(task.category, f"Task missing category: {task!r}")


# ── CreateVlanTask ─────────────────────────────────────────────────────────────

class TestCreateVlanTask(unittest.TestCase):

    def setUp(self):
        self.task = CreateVlanTask()

    def test_validate_inputs_ok(self):
        errors = self.task.validate_inputs({"vlan_id": "10", "vlan_name": ""})
        self.assertEqual(errors, [])

    def test_validate_inputs_missing_vlan_id(self):
        errors = self.task.validate_inputs({"vlan_id": "", "vlan_name": ""})
        self.assertTrue(any("VLAN ID" in e for e in errors))

    def test_validate_inputs_bad_vlan_id(self):
        errors = self.task.validate_inputs({"vlan_id": "9999"})
        self.assertTrue(len(errors) > 0)

    def test_validate_against_config_already_exists(self):
        cfg = "vlan 10\n name MGMT\n"
        warnings = self.task.validate_against_config(
            {"vlan_id": "10"}, cfg, "Cisco")
        self.assertTrue(len(warnings) > 0)
        self.assertIn("already exists", warnings[0])

    def test_validate_against_config_does_not_exist(self):
        cfg = "hostname Switch\n"
        warnings = self.task.validate_against_config(
            {"vlan_id": "20"}, cfg, "Cisco")
        self.assertEqual(warnings, [])

    def test_generate_commands_cisco_no_name(self):
        cmds = self.task.generate_commands({"vlan_id": "10", "vlan_name": ""}, "Cisco")
        self.assertIn("vlan 10", cmds)

    def test_generate_commands_cisco_with_name(self):
        cmds = self.task.generate_commands({"vlan_id": "10", "vlan_name": "MGMT"}, "Cisco")
        self.assertIn(" name MGMT", cmds)

    def test_generate_commands_huawei(self):
        cmds = self.task.generate_commands({"vlan_id": "10", "vlan_name": "MGMT"}, "Huawei")
        self.assertIn("vlan 10", cmds)
        self.assertIn(" description MGMT", cmds)
        self.assertIn("quit", cmds)

    def test_generate_rollback_cisco(self):
        cmds = self.task.generate_rollback({"vlan_id": "10"}, "Cisco")
        self.assertIn("no vlan 10", cmds)

    def test_generate_rollback_huawei(self):
        cmds = self.task.generate_rollback({"vlan_id": "10"}, "Huawei")
        self.assertIn("undo vlan 10", cmds)


# ── DeleteVlanTask ─────────────────────────────────────────────────────────────

class TestDeleteVlanTask(unittest.TestCase):

    def setUp(self):
        self.task = DeleteVlanTask()

    def test_validate_against_config_exists(self):
        cfg = "vlan 20\n"
        warnings = self.task.validate_against_config({"vlan_id": "20"}, cfg, "Cisco")
        self.assertEqual(warnings, [])

    def test_validate_against_config_not_exists(self):
        cfg = "hostname Switch\n"
        warnings = self.task.validate_against_config({"vlan_id": "20"}, cfg, "Cisco")
        self.assertTrue(len(warnings) > 0)

    def test_generate_commands_cisco(self):
        cmds = self.task.generate_commands({"vlan_id": "20"}, "Cisco")
        self.assertIn("no vlan 20", cmds)

    def test_generate_commands_huawei(self):
        cmds = self.task.generate_commands({"vlan_id": "20"}, "Huawei")
        self.assertIn("undo vlan 20", cmds)


# ── AccessPortTask ─────────────────────────────────────────────────────────────

class TestAccessPortTask(unittest.TestCase):

    def setUp(self):
        self.task = AccessPortTask()

    def test_generate_commands_cisco(self):
        cmds = self.task.generate_commands(
            {"interface": "Gi0/1", "vlan_id": "10"}, "Cisco")
        self.assertIn("interface Gi0/1", cmds)
        self.assertIn(" switchport mode access", cmds)
        self.assertIn(" switchport access vlan 10", cmds)

    def test_generate_commands_huawei(self):
        cmds = self.task.generate_commands(
            {"interface": "GE0/0/1", "vlan_id": "10"}, "Huawei")
        self.assertIn("interface GE0/0/1", cmds)
        self.assertIn(" port link-type access", cmds)
        self.assertIn(" port default vlan 10", cmds)

    def test_validate_missing_vlan_warns(self):
        cfg = "hostname Switch\n"
        warnings = self.task.validate_against_config(
            {"interface": "Gi0/1", "vlan_id": "10"}, cfg, "Cisco")
        self.assertTrue(any("does not exist" in w for w in warnings))


# ── HostnameTask ───────────────────────────────────────────────────────────────

class TestHostnameTask(unittest.TestCase):

    def setUp(self):
        self.task = HostnameTask()

    def test_validate_inputs_valid(self):
        errors = self.task.validate_inputs({"hostname": "Core-SW01"})
        self.assertEqual(errors, [])

    def test_validate_inputs_invalid(self):
        errors = self.task.validate_inputs({"hostname": "-bad"})
        self.assertTrue(len(errors) > 0)

    def test_validate_against_config_already_set(self):
        cfg = "hostname Core-SW01\n"
        warnings = self.task.validate_against_config(
            {"hostname": "Core-SW01"}, cfg, "Cisco")
        self.assertTrue(len(warnings) > 0)

    def test_generate_commands_cisco(self):
        cmds = self.task.generate_commands({"hostname": "R1"}, "Cisco")
        self.assertEqual(cmds, ["hostname R1"])

    def test_generate_commands_huawei(self):
        cmds = self.task.generate_commands({"hostname": "R1"}, "Huawei")
        self.assertEqual(cmds, ["sysname R1"])


# ── StaticRouteTask ────────────────────────────────────────────────────────────

class TestStaticRouteTask(unittest.TestCase):

    def setUp(self):
        self.task = StaticRouteTask()

    def test_validate_inputs_valid(self):
        errors = self.task.validate_inputs({
            "network": "10.0.0.0",
            "mask": "255.255.255.0",
            "next_hop": "192.168.1.1",
            "distance": "1",
        })
        self.assertEqual(errors, [])

    def test_validate_inputs_bad_network(self):
        errors = self.task.validate_inputs({
            "network": "999.999.999.0",
            "mask": "255.255.255.0",
            "next_hop": "192.168.1.1",
        })
        self.assertTrue(len(errors) > 0)

    def test_generate_commands_cisco_dotted(self):
        cmds = self.task.generate_commands({
            "network": "10.0.0.0",
            "mask": "255.255.255.0",
            "next_hop": "192.168.1.1",
            "distance": "1",
        }, "Cisco")
        self.assertTrue(any("ip route 10.0.0.0" in c for c in cmds))

    def test_generate_commands_cisco_prefix(self):
        cmds = self.task.generate_commands({
            "network": "10.0.0.0",
            "mask": "/24",
            "next_hop": "192.168.1.1",
            "distance": "",
        }, "Cisco")
        self.assertTrue(any("ip route 10.0.0.0" in c for c in cmds))

    def test_generate_commands_huawei(self):
        cmds = self.task.generate_commands({
            "network": "10.0.0.0",
            "mask": "/24",
            "next_hop": "192.168.1.1",
            "distance": "1",
        }, "Huawei")
        self.assertTrue(any("ip route-static" in c for c in cmds))

    def test_generate_rollback_cisco(self):
        cmds = self.task.generate_rollback({
            "network": "10.0.0.0",
            "mask": "255.255.255.0",
            "next_hop": "192.168.1.1",
        }, "Cisco")
        self.assertTrue(any("no ip route" in c for c in cmds))


# ── NtpTask ────────────────────────────────────────────────────────────────────

class TestNtpTask(unittest.TestCase):

    def setUp(self):
        self.task = NtpTask()

    def test_generate_commands_cisco_single(self):
        cmds = self.task.generate_commands(
            {"ntp_server": "1.2.3.4", "ntp_server2": "", "timezone": ""}, "Cisco")
        self.assertIn("ntp server 1.2.3.4", cmds)

    def test_generate_commands_cisco_two_servers(self):
        cmds = self.task.generate_commands(
            {"ntp_server": "1.2.3.4", "ntp_server2": "5.6.7.8", "timezone": ""}, "Cisco")
        self.assertIn("ntp server 1.2.3.4", cmds)
        self.assertIn("ntp server 5.6.7.8", cmds)

    def test_generate_commands_huawei(self):
        cmds = self.task.generate_commands(
            {"ntp_server": "1.2.3.4", "ntp_server2": "", "timezone": ""}, "Huawei")
        self.assertIn("ntp-server 1.2.3.4", cmds)

    def test_validate_already_configured(self):
        cfg = "ntp server 1.2.3.4\n"
        warnings = self.task.validate_against_config(
            {"ntp_server": "1.2.3.4"}, cfg, "Cisco")
        self.assertTrue(len(warnings) > 0)


# ── SnmpTask ───────────────────────────────────────────────────────────────────

class TestSnmpTask(unittest.TestCase):

    def setUp(self):
        self.task = SnmpTask()

    def test_generate_commands_cisco(self):
        cmds = self.task.generate_commands({
            "community": "public",
            "permission": "RO",
            "snmp_version": "2c",
            "trap_host": "",
        }, "Cisco")
        self.assertTrue(any("snmp-server community public" in c for c in cmds))

    def test_generate_commands_with_trap(self):
        cmds = self.task.generate_commands({
            "community": "public",
            "permission": "RO",
            "snmp_version": "2c",
            "trap_host": "10.0.0.1",
        }, "Cisco")
        self.assertTrue(any("snmp-server host" in c for c in cmds))

    def test_generate_rollback_cisco(self):
        cmds = self.task.generate_rollback(
            {"community": "public", "permission": "RO"}, "Cisco")
        self.assertIn("no snmp-server community public", cmds)


# ── BackupTask ─────────────────────────────────────────────────────────────────

class TestBackupTask(unittest.TestCase):

    def setUp(self):
        self.task = BackupTask()

    def test_generate_commands_cisco_full(self):
        cmds = self.task.generate_commands({"backup_type": "full"}, "Cisco")
        self.assertEqual(cmds, ["show running-config"])

    def test_generate_commands_cisco_interfaces(self):
        cmds = self.task.generate_commands(
            {"backup_type": "interfaces only"}, "Cisco")
        self.assertIn("show running-config | section interface", cmds)

    def test_generate_commands_huawei(self):
        cmds = self.task.generate_commands({"backup_type": "full"}, "Huawei")
        self.assertEqual(cmds, ["display current-configuration"])


if __name__ == "__main__":
    unittest.main()
