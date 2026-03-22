"""
Compliance Checking Module
Validates device configurations against compliance rules
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from .logger import get_observability_manager


class ComplianceChecker:
    """Checks device configurations against compliance rules"""

    # Default compliance rules
    DEFAULT_RULES = {
        "cisco": {
            "ssh_enabled": {"pattern": "ip ssh version 2", "required": True},
            "dns_configured": {"pattern": "ip name-server", "required": True},
            "logging_enabled": {"pattern": "logging", "required": True},
            "ntp_configured": {"pattern": "ntp server", "required": True},
            "snmp_configured": {"pattern": "snmp-server", "required": True},
        },
        "huawei": {
            "ssh_enabled": {"pattern": "stelnet server enable", "required": True},
            "dns_configured": {"pattern": "dns server", "required": True},
            "logging_enabled": {"pattern": "logging", "required": True},
            "ntp_configured": {"pattern": "ntp-server", "required": True},
            "snmp_configured": {"pattern": "snmp-agent", "required": True},
        }
    }

    def __init__(self, rules_file: str = "data/compliance_rules.json"):
        self.rules_file = Path(rules_file)
        self.logger = get_observability_manager()
        self.rules = self._load_rules()
        self.compliance_records = {}

    def _load_rules(self) -> Dict:
        """Load compliance rules from file"""
        if self.rules_file.exists():
            with open(self.rules_file, 'r') as f:
                return json.load(f)
        
        # Save default rules
        self.rules_file.parent.mkdir(exist_ok=True)
        with open(self.rules_file, 'w') as f:
            json.dump(self.DEFAULT_RULES, f, indent=2)
        
        return self.DEFAULT_RULES

    def check_device_compliance(self, hostname: str, vendor: str,
                               config_content: str) -> Dict:
        """Check if device configuration complies with rules"""
        try:
            vendor_lower = vendor.lower()
            if vendor_lower not in self.rules:
                return {"error": f"No rules for vendor: {vendor}"}
            
            rules = self.rules[vendor_lower]
            results = {
                "hostname": hostname,
                "vendor": vendor,
                "timestamp": datetime.now().isoformat(),
                "checks": {},
                "passed": 0,
                "failed": 0,
                "warnings": 0
            }
            
            for rule_name, rule_def in rules.items():
                is_compliant = self._check_rule(config_content, rule_def)
                
                check_result = {
                    "rule": rule_name,
                    "required": rule_def.get("required", True),
                    "compliant": is_compliant,
                    "pattern": rule_def.get("pattern")
                }
                
                results["checks"][rule_name] = check_result
                
                if is_compliant:
                    results["passed"] += 1
                else:
                    if rule_def.get("required", True):
                        results["failed"] += 1
                    else:
                        results["warnings"] += 1
            
            results["overall_compliance"] = results["failed"] == 0
            results["compliance_score"] = (results["passed"] / 
                                         (results["passed"] + results["failed"] + results["warnings"])) * 100
            
            # Store record
            self.compliance_records[hostname] = results
            
            # Log the check
            self.logger.log_event(
                event_type="compliance_check",
                device_name=hostname,
                description=f"Compliance check completed: {results['compliance_score']:.0f}% compliant",
                status="success",
                details={
                    "passed": results["passed"],
                    "failed": results["failed"],
                    "score": results["compliance_score"]
                }
            )
            
            return results
        
        except Exception as e:
            self.logger.log_error(hostname, str(e), "compliance_check_error")
            return {"error": f"Compliance check failed: {str(e)}"}

    @staticmethod
    def _check_rule(config_content: str, rule_def: Dict) -> bool:
        """Check if config satisfies a rule"""
        pattern = rule_def.get("pattern", "")
        return pattern.lower() in config_content.lower()

    def add_custom_rule(self, vendor: str, rule_name: str,
                       pattern: str, required: bool = True) -> Tuple[bool, str]:
        """Add a custom compliance rule"""
        try:
            vendor_lower = vendor.lower()
            
            if vendor_lower not in self.rules:
                self.rules[vendor_lower] = {}
            
            self.rules[vendor_lower][rule_name] = {
                "pattern": pattern,
                "required": required
            }
            
            with open(self.rules_file, 'w') as f:
                json.dump(self.rules, f, indent=2)
            
            self.logger.log_event(
                event_type="rule_added",
                device_name=None,
                description=f"Compliance rule added: {rule_name} for {vendor}",
                status="success"
            )
            
            return True, f"Rule {rule_name} added successfully"
        
        except Exception as e:
            self.logger.log_error(None, str(e), "add_rule_error")
            return False, f"Failed to add rule: {str(e)}"

    def get_device_compliance_history(self, hostname: str) -> Optional[Dict]:
        """Get compliance check history for device"""
        return self.compliance_records.get(hostname)

    def get_compliance_report(self) -> Dict:
        """Generate compliance report for all devices"""
        report = {
            "generated": datetime.now().isoformat(),
            "total_devices_checked": len(self.compliance_records),
            "compliant_devices": len([d for d in self.compliance_records.values()
                                     if d.get("overall_compliance", False)]),
            "non_compliant_devices": len([d for d in self.compliance_records.values()
                                         if not d.get("overall_compliance", True)]),
            "average_compliance_score": 0,
            "devices": {}
        }
        
        if self.compliance_records:
            scores = [d.get("compliance_score", 0) for d in self.compliance_records.values()]
            report["average_compliance_score"] = sum(scores) / len(scores)
        
        for hostname, compliance_data in self.compliance_records.items():
            report["devices"][hostname] = {
                "compliant": compliance_data.get("overall_compliance", False),
                "score": compliance_data.get("compliance_score", 0),
                "passed": compliance_data.get("passed", 0),
                "failed": compliance_data.get("failed", 0),
                "timestamp": compliance_data.get("timestamp")
            }
        
        return report

    def generate_compliance_evidence(self, hostname: str) -> Dict:
        """Generate evidence for compliance audit"""
        compliance_record = self.compliance_records.get(hostname)
        if not compliance_record:
            return {"error": "No compliance record found"}
        
        evidence = {
            "hostname": hostname,
            "vendor": compliance_record.get("vendor"),
            "audit_date": datetime.now().isoformat(),
            "overall_result": "PASS" if compliance_record.get("overall_compliance") else "FAIL",
            "score": compliance_record.get("compliance_score"),
            "checks": {}
        }
        
        for check_name, check_data in compliance_record.get("checks", {}).items():
            evidence["checks"][check_name] = {
                "status": "PASS" if check_data.get("compliant") else "FAIL",
                "required": check_data.get("required"),
                "pattern_checked": check_data.get("pattern")
            }
        
        return evidence

    def export_compliance_report(self, format_type: str = "json") -> Tuple[bool, str]:
        """Export compliance report in various formats"""
        try:
            report = self.get_compliance_report()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if format_type == "json":
                filename = f"compliance_report_{timestamp}.json"
                content = json.dumps(report, indent=2)
            elif format_type == "text":
                filename = f"compliance_report_{timestamp}.txt"
                content = self._format_report_text(report)
            else:
                return False, f"Unsupported format: {format_type}"
            
            filepath = Path("reports") / filename
            filepath.parent.mkdir(exist_ok=True)
            
            with open(filepath, 'w') as f:
                f.write(content)
            
            return True, f"Report exported: {filename}"
        
        except Exception as e:
            self.logger.log_error(None, str(e), "export_error")
            return False, f"Export failed: {str(e)}"

    @staticmethod
    def _format_report_text(report: Dict) -> str:
        """Format compliance report as text"""
        lines = [
            "=" * 60,
            "COMPLIANCE REPORT",
            "=" * 60,
            f"Generated: {report['generated']}",
            f"Total Devices Checked: {report['total_devices_checked']}",
            f"Compliant Devices: {report['compliant_devices']}",
            f"Non-Compliant Devices: {report['non_compliant_devices']}",
            f"Average Compliance Score: {report['average_compliance_score']:.1f}%",
            "=" * 60,
            ""
        ]
        
        for hostname, device_info in report["devices"].items():
            lines.append(f"Device: {hostname}")
            lines.append(f"  Status: {'COMPLIANT' if device_info['compliant'] else 'NON-COMPLIANT'}")
            lines.append(f"  Score: {device_info['score']:.1f}%")
            lines.append(f"  Passed: {device_info['passed']}, Failed: {device_info['failed']}")
            lines.append("")
        
        return "\n".join(lines)
