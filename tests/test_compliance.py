"""
Unit tests for modules/compliance.py
"""

import unittest
from modules.compliance import ComplianceChecker


class TestCheckRule(unittest.TestCase):
    """Tests for ComplianceChecker._check_rule()"""

    def _rule(self, pattern: str, required: bool = True) -> dict:
        return {"pattern": pattern, "required": required}

    # --- Basic matching ---

    def test_match_present(self):
        config = "ip ssh version 2\nlogging 10.0.0.1\n"
        self.assertTrue(ComplianceChecker._check_rule(config, self._rule("ip ssh version 2")))

    def test_match_case_insensitive(self):
        config = "IP SSH VERSION 2\n"
        self.assertTrue(ComplianceChecker._check_rule(config, self._rule("ip ssh version 2")))

    def test_match_absent(self):
        config = "hostname router1\ninterface GE0/0\n"
        self.assertFalse(ComplianceChecker._check_rule(config, self._rule("ip ssh version 2")))

    # --- Negation / comment handling ---

    def test_commented_out_cisco_bang(self):
        """A pattern on a commented-out (!) line should NOT match."""
        config = "! ip ssh version 2\n"
        self.assertFalse(ComplianceChecker._check_rule(config, self._rule("ip ssh version 2")))

    def test_commented_out_hash(self):
        """A pattern on a # comment line should NOT match."""
        config = "# ip ssh version 2\n"
        self.assertFalse(ComplianceChecker._check_rule(config, self._rule("ip ssh version 2")))

    def test_negated_no_command(self):
        """A 'no <pattern>' line should NOT match."""
        config = "no ip ssh version 2\n"
        self.assertFalse(ComplianceChecker._check_rule(config, self._rule("ip ssh version 2")))

    def test_negated_then_present(self):
        """Negated line followed by active line — should match."""
        config = "no ip ssh version 2\nip ssh version 2\n"
        self.assertTrue(ComplianceChecker._check_rule(config, self._rule("ip ssh version 2")))

    def test_empty_pattern(self):
        """Empty pattern should never match."""
        self.assertFalse(ComplianceChecker._check_rule("anything", self._rule("")))

    def test_empty_config(self):
        self.assertFalse(ComplianceChecker._check_rule("", self._rule("ntp server")))

    # --- Special characters in patterns ---

    def test_pattern_with_hyphen(self):
        config = "ntp-server 10.0.0.1\n"
        self.assertTrue(ComplianceChecker._check_rule(config, self._rule("ntp-server")))

    def test_pattern_not_partial_false_match(self):
        """'logging' in a comment should NOT match."""
        config = "! logging disabled\n"
        self.assertFalse(ComplianceChecker._check_rule(config, self._rule("logging")))


class TestCheckDeviceCompliance(unittest.TestCase):
    """Integration-style tests for check_device_compliance()"""

    CISCO_CONFIG_COMPLIANT = """
version 15.0
hostname router1
ip ssh version 2
ip name-server 8.8.8.8
logging 10.0.0.1
ntp server 10.0.0.2
snmp-server community public RO
"""

    CISCO_CONFIG_MISSING_SSH = """
version 15.0
hostname router1
ip name-server 8.8.8.8
logging 10.0.0.1
ntp server 10.0.0.2
snmp-server community public RO
"""

    def setUp(self):
        self.checker = ComplianceChecker.__new__(ComplianceChecker)
        self.checker.rules = ComplianceChecker.DEFAULT_RULES
        self.checker.compliance_records = {}
        # Provide a no-op logger
        class _NoOpLogger:
            def log_event(self, **kw): pass
            def log_error(self, *a, **kw): pass
        self.checker.logger = _NoOpLogger()

    def test_fully_compliant_cisco(self):
        result = self.checker.check_device_compliance("r1", "Cisco", self.CISCO_CONFIG_COMPLIANT)
        self.assertTrue(result["overall_compliance"])
        self.assertEqual(result["failed"], 0)
        self.assertGreater(result["compliance_score"], 99)

    def test_non_compliant_cisco_missing_ssh(self):
        result = self.checker.check_device_compliance("r1", "Cisco", self.CISCO_CONFIG_MISSING_SSH)
        self.assertFalse(result["overall_compliance"])
        self.assertGreater(result["failed"], 0)
        self.assertFalse(result["checks"]["ssh_enabled"]["compliant"])

    def test_unknown_vendor_returns_error(self):
        result = self.checker.check_device_compliance("r1", "Juniper", "some config")
        self.assertIn("error", result)

    def test_compliance_score_range(self):
        result = self.checker.check_device_compliance("r1", "Cisco", self.CISCO_CONFIG_COMPLIANT)
        self.assertGreaterEqual(result["compliance_score"], 0)
        self.assertLessEqual(result["compliance_score"], 100)


if __name__ == "__main__":
    unittest.main()
