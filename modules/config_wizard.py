"""
Configuration Wizard Module
----------------------------
Defines structured, validated configuration tasks.

Each task follows the same contract:
  fields                 — input field definitions
  validate_inputs()      — checks raw form values (types, formats)
  validate_against_config() — checks against the device's running config
  generate_commands()    — returns the CLI commands to push
  generate_rollback()    — returns the undo/rollback commands
"""

import ipaddress
import re
from dataclasses import dataclass, field as dc_field
from typing import Callable, Dict, List, Optional


# ── Field definition ──────────────────────────────────────────────────────────

@dataclass
class Field:
    """One input field in a configuration task form."""
    name: str
    label: str
    field_type: str          # "text" | "integer" | "ip" | "select" | "password" | "multiline"
    required: bool = True
    hint: str = ""
    options: List[str] = dc_field(default_factory=list)   # for "select"
    default: str = ""
    validator: Optional[Callable[[str], Optional[str]]] = None


# ── Validators ────────────────────────────────────────────────────────────────

def _vlan_id(val: str) -> Optional[str]:
    try:
        n = int(val)
        if not (1 <= n <= 4094):
            return "VLAN ID must be 1–4094"
    except ValueError:
        return "VLAN ID must be a number"
    return None


def _vlan_list(val: str) -> Optional[str]:
    """Validates '10,20,30-40' style VLAN lists."""
    if val.lower() == "all":
        return None
    for part in val.split(","):
        part = part.strip()
        if "-" in part:
            a, _, b = part.partition("-")
            try:
                if not (1 <= int(a) <= 4094 and 1 <= int(b) <= 4094 and int(a) <= int(b)):
                    return f"VLAN range '{part}' is invalid"
            except ValueError:
                return f"VLAN range '{part}' is not numeric"
        else:
            err = _vlan_id(part)
            if err:
                return err
    return None


def _hostname(val: str) -> Optional[str]:
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9\-]{0,62}$", val):
        return "Letters, digits, hyphens only (max 63 chars, must start with letter/digit)"
    return None


def _ip(val: str) -> Optional[str]:
    try:
        ipaddress.ip_address(val)
    except ValueError:
        return f"'{val}' is not a valid IP address"
    return None


def _port(val: str) -> Optional[str]:
    try:
        n = int(val)
        if not (1 <= n <= 65535):
            return "Port must be 1–65535"
    except ValueError:
        return "Port must be a number"
    return None


def _community(val: str) -> Optional[str]:
    if not re.match(r"^[a-zA-Z0-9_\-.@]{1,32}$", val):
        return "1–32 alphanumeric/underscore characters"
    return None


def _admin_distance(val: str) -> Optional[str]:
    try:
        n = int(val)
        if not (1 <= n <= 255):
            return "Admin distance must be 1–255"
    except ValueError:
        return "Must be a number"
    return None


# ── Base task ─────────────────────────────────────────────────────────────────

class ConfigTask:
    """Base class — all concrete tasks inherit from this."""
    name: str = ""
    description: str = ""
    category: str = ""
    supported_vendors: List[str] = ["Cisco", "Huawei"]

    @property
    def fields(self) -> List[Field]:
        return []

    def validate_inputs(self, inputs: Dict[str, str]) -> List[str]:
        """Validate raw form values. Returns a list of error strings (empty = OK)."""
        errors = []
        for f in self.fields:
            val = inputs.get(f.name, "").strip()
            if f.required and not val:
                errors.append(f"'{f.label}' is required")
                continue
            if val and f.validator:
                err = f.validator(val)
                if err:
                    errors.append(f"[{f.label}] {err}")
        return errors

    def validate_against_config(self, inputs: Dict[str, str],
                                running_config: str, vendor: str) -> List[str]:
        """
        Cross-check inputs against the device's running config.
        Returns a list of warning/error strings (empty = OK).
        """
        return []

    def generate_commands(self, inputs: Dict[str, str], vendor: str) -> List[str]:
        """Return the list of CLI commands to push."""
        return []

    def generate_rollback(self, inputs: Dict[str, str], vendor: str) -> List[str]:
        """Return the undo/rollback CLI commands."""
        return []


# ── Helper ────────────────────────────────────────────────────────────────────

def _exists_in_config(pattern: str, config: str) -> bool:
    return bool(re.search(pattern, config, re.MULTILINE | re.IGNORECASE))


# ══════════════════════════════════════════════════════════════════════════════
# Task Definitions
# ══════════════════════════════════════════════════════════════════════════════

class BackupTask(ConfigTask):
    name        = "Backup Running Config"
    description = "Fetch and save the device's running configuration via SSH."
    category    = "Maintenance"

    @property
    def fields(self) -> List[Field]:
        return [
            Field("backup_type", "Backup Scope", "select",
                  options=["full", "interfaces only", "routing only"],
                  default="full",
                  hint="Section of config to retrieve"),
        ]

    def generate_commands(self, inputs, vendor) -> List[str]:
        scope = inputs.get("backup_type", "full")
        if vendor == "Huawei":
            return ["display current-configuration"]
        cmd_map = {
            "full":             "show running-config",
            "interfaces only":  "show running-config | section interface",
            "routing only":     "show running-config | section router",
        }
        return [cmd_map.get(scope, "show running-config")]


# ── VLAN tasks ────────────────────────────────────────────────────────────────

class CreateVlanTask(ConfigTask):
    name        = "Create VLAN"
    description = "Create a new VLAN with an optional descriptive name."
    category    = "VLAN"

    @property
    def fields(self) -> List[Field]:
        return [
            Field("vlan_id",   "VLAN ID",   "integer", validator=_vlan_id,
                  hint="1–4094"),
            Field("vlan_name", "VLAN Name", "text", required=False,
                  hint="Optional label, e.g. MGMT or SERVERS"),
        ]

    def validate_against_config(self, inputs, running_config, vendor) -> List[str]:
        vid = inputs.get("vlan_id", "").strip()
        if _exists_in_config(rf"^\s*vlan\s+{re.escape(vid)}\s*$", running_config):
            return [f"VLAN {vid} already exists on this device"]
        return []

    def generate_commands(self, inputs, vendor) -> List[str]:
        vid  = inputs["vlan_id"].strip()
        name = inputs.get("vlan_name", "").strip()
        if vendor == "Huawei":
            cmds = [f"vlan {vid}"]
            if name:
                cmds.append(f" description {name}")
            cmds.append("quit")
        else:
            cmds = [f"vlan {vid}"]
            if name:
                cmds.append(f" name {name}")
        return cmds

    def generate_rollback(self, inputs, vendor) -> List[str]:
        vid = inputs["vlan_id"].strip()
        return [f"undo vlan {vid}"] if vendor == "Huawei" else [f"no vlan {vid}"]


class DeleteVlanTask(ConfigTask):
    name        = "Delete VLAN"
    description = "Remove a VLAN from the device VLAN database."
    category    = "VLAN"

    @property
    def fields(self) -> List[Field]:
        return [
            Field("vlan_id", "VLAN ID", "integer", validator=_vlan_id, hint="1–4094"),
        ]

    def validate_against_config(self, inputs, running_config, vendor) -> List[str]:
        vid = inputs.get("vlan_id", "").strip()
        if not _exists_in_config(rf"^\s*vlan\s+{re.escape(vid)}\s*$", running_config):
            return [f"VLAN {vid} does not exist on this device"]
        return []

    def generate_commands(self, inputs, vendor) -> List[str]:
        vid = inputs["vlan_id"].strip()
        return [f"undo vlan {vid}"] if vendor == "Huawei" else [f"no vlan {vid}"]

    def generate_rollback(self, inputs, vendor) -> List[str]:
        return []   # Deletion cannot be auto-rolled back


class AccessPortTask(ConfigTask):
    name        = "Assign Access Port"
    description = "Set an interface to access mode and bind it to a VLAN."
    category    = "VLAN"

    @property
    def fields(self) -> List[Field]:
        return [
            Field("interface", "Interface", "text",
                  hint="e.g. GigabitEthernet0/1  or  Gi0/1  or  GE0/0/1"),
            Field("vlan_id",   "VLAN ID",   "integer", validator=_vlan_id,
                  hint="The VLAN must already exist on the device"),
        ]

    def validate_against_config(self, inputs, running_config, vendor) -> List[str]:
        errors = []
        vid   = inputs.get("vlan_id",   "").strip()
        intf  = inputs.get("interface", "").strip()
        if not _exists_in_config(rf"^\s*vlan\s+{re.escape(vid)}\s*$", running_config):
            errors.append(f"VLAN {vid} does not exist — create it first")
        if _exists_in_config(r"switchport mode trunk", running_config):
            errors.append(f"Interface {intf} appears to already be a trunk — verify first")
        return errors

    def generate_commands(self, inputs, vendor) -> List[str]:
        intf = inputs["interface"].strip()
        vid  = inputs["vlan_id"].strip()
        if vendor == "Huawei":
            return [f"interface {intf}", " port link-type access",
                    f" port default vlan {vid}", "quit"]
        return [f"interface {intf}", " switchport mode access",
                f" switchport access vlan {vid}"]

    def generate_rollback(self, inputs, vendor) -> List[str]:
        intf = inputs["interface"].strip()
        if vendor == "Huawei":
            return [f"interface {intf}", " undo port default vlan", "quit"]
        return [f"interface {intf}", " no switchport access vlan"]


class TrunkPortTask(ConfigTask):
    name        = "Configure Trunk Port"
    description = "Set an interface to trunk mode and define allowed VLANs."
    category    = "VLAN"

    @property
    def fields(self) -> List[Field]:
        return [
            Field("interface",    "Interface",    "text",
                  hint="e.g. GigabitEthernet0/1"),
            Field("allowed_vlans","Allowed VLANs","text", validator=_vlan_list,
                  hint="10,20,30-40  or  all"),
            Field("native_vlan",  "Native VLAN",  "integer", required=False,
                  validator=_vlan_id, hint="Optional native VLAN (default 1)"),
        ]

    def validate_against_config(self, inputs, running_config, vendor) -> List[str]:
        errors = []
        vlans = inputs.get("allowed_vlans", "").strip()
        if vlans.lower() != "all":
            for part in vlans.split(","):
                part = part.strip()
                if "-" in part:
                    continue    # skip range check against config
                if not _exists_in_config(rf"^\s*vlan\s+{re.escape(part)}\s*$",
                                         running_config):
                    errors.append(f"VLAN {part} does not exist — create it first")
        return errors

    def generate_commands(self, inputs, vendor) -> List[str]:
        intf   = inputs["interface"].strip()
        vlans  = inputs["allowed_vlans"].strip()
        native = inputs.get("native_vlan", "").strip()
        if vendor == "Huawei":
            cmds = [f"interface {intf}", " port link-type trunk",
                    f" port trunk allow-pass vlan {vlans}"]
            if native:
                cmds.append(f" port trunk pvid vlan {native}")
            cmds.append("quit")
        else:
            cmds = [f"interface {intf}", " switchport mode trunk",
                    f" switchport trunk allowed vlan {vlans}"]
            if native:
                cmds.append(f" switchport trunk native vlan {native}")
        return cmds

    def generate_rollback(self, inputs, vendor) -> List[str]:
        intf = inputs["interface"].strip()
        if vendor == "Huawei":
            return [f"interface {intf}", " undo port link-type", "quit"]
        return [f"interface {intf}", " no switchport mode trunk"]


# ── Basic Config tasks ────────────────────────────────────────────────────────

class HostnameTask(ConfigTask):
    name        = "Set Hostname"
    description = "Change the device hostname/sysname."
    category    = "Basic Config"

    @property
    def fields(self) -> List[Field]:
        return [
            Field("hostname", "New Hostname", "text", validator=_hostname,
                  hint="Letters, digits, hyphens (max 63 chars)"),
        ]

    def validate_against_config(self, inputs, running_config, vendor) -> List[str]:
        new_name = inputs.get("hostname", "").strip()
        pattern  = r"^sysname\s+(\S+)" if vendor == "Huawei" else r"^hostname\s+(\S+)"
        m = re.search(pattern, running_config, re.MULTILINE | re.IGNORECASE)
        if m and m.group(1) == new_name:
            return [f"Hostname is already '{new_name}'"]
        return []

    def generate_commands(self, inputs, vendor) -> List[str]:
        name = inputs["hostname"].strip()
        return [f"sysname {name}"] if vendor == "Huawei" else [f"hostname {name}"]

    def generate_rollback(self, inputs, vendor) -> List[str]:
        return []   # Original hostname not known without prior fetch


class PortDescriptionTask(ConfigTask):
    name        = "Set Port Description"
    description = "Add or update a description label on an interface."
    category    = "Basic Config"

    @property
    def fields(self) -> List[Field]:
        return [
            Field("interface",   "Interface",   "text",
                  hint="e.g. GigabitEthernet0/1"),
            Field("description", "Description", "text",
                  hint="Free-text label for the port (e.g. Uplink-to-Core)"),
        ]

    def generate_commands(self, inputs, vendor) -> List[str]:
        intf = inputs["interface"].strip()
        desc = inputs["description"].strip()
        if vendor == "Huawei":
            return [f"interface {intf}", f" description {desc}", "quit"]
        return [f"interface {intf}", f" description {desc}"]

    def generate_rollback(self, inputs, vendor) -> List[str]:
        intf = inputs["interface"].strip()
        if vendor == "Huawei":
            return [f"interface {intf}", " undo description", "quit"]
        return [f"interface {intf}", " no description"]


class InterfaceShutdownTask(ConfigTask):
    name        = "Shutdown / No Shutdown Interface"
    description = "Administratively enable or disable an interface."
    category    = "Basic Config"

    @property
    def fields(self) -> List[Field]:
        return [
            Field("interface", "Interface", "text",
                  hint="e.g. GigabitEthernet0/1"),
            Field("action", "Action", "select",
                  options=["shutdown", "no shutdown"], default="shutdown",
                  hint="shutdown = disable,  no shutdown = enable"),
        ]

    def generate_commands(self, inputs, vendor) -> List[str]:
        intf   = inputs["interface"].strip()
        action = inputs.get("action", "shutdown")
        if vendor == "Huawei":
            cmd = "shutdown" if action == "shutdown" else "undo shutdown"
            return [f"interface {intf}", f" {cmd}", "quit"]
        return [f"interface {intf}", f" {action}"]

    def generate_rollback(self, inputs, vendor) -> List[str]:
        intf   = inputs["interface"].strip()
        action = inputs.get("action", "shutdown")
        reverse = "no shutdown" if action == "shutdown" else "shutdown"
        if vendor == "Huawei":
            cmd = "undo shutdown" if reverse == "no shutdown" else "shutdown"
            return [f"interface {intf}", f" {cmd}", "quit"]
        return [f"interface {intf}", f" {reverse}"]


class BannerTask(ConfigTask):
    name        = "Set Login Banner"
    description = "Configure the MOTD (Message of the Day) login banner."
    category    = "Basic Config"

    @property
    def fields(self) -> List[Field]:
        return [
            Field("banner_text", "Banner Text", "multiline",
                  hint="Text shown at login. Do not use # or ^ characters."),
        ]

    def generate_commands(self, inputs, vendor) -> List[str]:
        text = inputs.get("banner_text", "").strip()
        if vendor == "Huawei":
            return [f'header login information "{text}"']
        return [f"banner motd ^{text}^"]

    def generate_rollback(self, inputs, vendor) -> List[str]:
        return ["undo header login"] if vendor == "Huawei" else ["no banner motd"]


# ── Security tasks ────────────────────────────────────────────────────────────

class SshEnableTask(ConfigTask):
    name        = "Enable SSH"
    description = "Enable SSH (v2) on the device and restrict VTY lines to SSH-only."
    category    = "Security"

    @property
    def fields(self) -> List[Field]:
        return [
            Field("domain_name", "Domain Name", "text", required=False,
                  hint="Cisco only: required for RSA key generation (e.g. company.local)"),
            Field("key_size", "RSA Key Size", "select",
                  options=["1024", "2048", "4096"], default="2048",
                  hint="RSA modulus bits (Cisco only)"),
            Field("ssh_version", "SSH Version", "select",
                  options=["2", "1"], default="2",
                  hint="Version 2 is strongly recommended"),
        ]

    def validate_against_config(self, inputs, running_config, vendor) -> List[str]:
        ver = inputs.get("ssh_version", "2")
        if vendor == "Cisco":
            if _exists_in_config(rf"ip ssh version {re.escape(ver)}", running_config):
                return [f"SSH version {ver} already configured"]
        elif vendor == "Huawei":
            if _exists_in_config(r"stelnet server enable", running_config):
                return ["Stelnet (SSH) server is already enabled"]
        return []

    def generate_commands(self, inputs, vendor) -> List[str]:
        domain  = inputs.get("domain_name", "").strip()
        keysize = inputs.get("key_size", "2048")
        ver     = inputs.get("ssh_version", "2")
        if vendor == "Huawei":
            return ["stelnet server enable",
                    "ssh server-source -i LoopBack0"]
        cmds = []
        if domain:
            cmds.append(f"ip domain-name {domain}")
        cmds += [f"crypto key generate rsa modulus {keysize}",
                 f"ip ssh version {ver}",
                 "ip ssh time-out 60",
                 "ip ssh authentication-retries 3",
                 "line vty 0 4",
                 " transport input ssh",
                 " login local"]
        return cmds

    def generate_rollback(self, inputs, vendor) -> List[str]:
        if vendor == "Huawei":
            return ["undo stelnet server enable"]
        return ["crypto key zeroize rsa", "no ip ssh version"]


class LdapTask(ConfigTask):
    name        = "Configure LDAP / AAA"
    description = "Configure LDAP authentication for management access (AAA)."
    category    = "Security"

    @property
    def fields(self) -> List[Field]:
        return [
            Field("server_ip",    "LDAP Server IP",       "ip",       validator=_ip,
                  hint="IP address of Active Directory / LDAP server"),
            Field("server_port",  "LDAP Port",            "integer",
                  default="389",  validator=_port,
                  hint="389 = LDAP,  636 = LDAPS"),
            Field("base_dn",      "Base DN",              "text",
                  hint="e.g. DC=company,DC=local"),
            Field("bind_dn",      "Bind DN (username)",   "text",
                  hint="e.g. CN=svc-net,OU=ServiceAccts,DC=company,DC=local"),
            Field("bind_password","Bind Password",        "password",
                  hint="Password for the bind account"),
            Field("profile_name", "Profile Name",         "text",
                  default="LDAP-CORP",
                  hint="Internal name for this LDAP profile"),
        ]

    def validate_against_config(self, inputs, running_config, vendor) -> List[str]:
        warnings = []
        name = inputs.get("profile_name", "").strip()
        ip   = inputs.get("server_ip",    "").strip()
        if vendor == "Cisco":
            if _exists_in_config(r"aaa new-model", running_config):
                warnings.append("AAA already enabled — new commands will be additive")
            if _exists_in_config(rf"ldap server.*{re.escape(ip)}", running_config):
                warnings.append(f"LDAP server {ip} may already be configured")
        elif vendor == "Huawei":
            if _exists_in_config(rf"ldap-server template {re.escape(name)}", running_config):
                warnings.append(f"LDAP profile '{name}' already exists — will overwrite")
        return warnings

    def generate_commands(self, inputs, vendor) -> List[str]:
        ip   = inputs["server_ip"].strip()
        port = inputs.get("server_port", "389").strip()
        base = inputs.get("base_dn",     "").strip()
        bind = inputs.get("bind_dn",     "").strip()
        pwd  = inputs.get("bind_password","").strip()
        name = inputs.get("profile_name","LDAP-CORP").strip()
        if vendor == "Huawei":
            return [f"ldap-server template {name}",
                    f" ldap-server ip {ip} port {port}",
                    f" ldap-server bind-dn {bind} password cipher {pwd}",
                    f" ldap-server base-dn {base}",
                    "quit",
                    "aaa",
                    "  authentication-scheme ldap-auth",
                    "   authentication-mode ldap",
                    "  quit",
                    f"  domain default",
                    f"   authentication-scheme ldap-auth",
                    f"   ldap-server {name}",
                    "  quit",
                    "quit"]
        return ["aaa new-model",
                f"ldap server {name}",
                f" ipv4 {ip}",
                f" port {port}",
                f" bind authenticate root-dn {bind} password {pwd}",
                f" base-dn {base}",
                "aaa authentication login default group ldap local",
                "aaa authorization exec default group ldap local"]

    def generate_rollback(self, inputs, vendor) -> List[str]:
        name = inputs.get("profile_name", "LDAP-CORP").strip()
        if vendor == "Huawei":
            return [f"undo ldap-server template {name}"]
        return [f"no ldap server {name}",
                "no aaa authentication login default group ldap local"]


# ── Monitoring tasks ──────────────────────────────────────────────────────────

class NtpTask(ConfigTask):
    name        = "Configure NTP"
    description = "Configure NTP servers for time synchronisation."
    category    = "Monitoring"

    @property
    def fields(self) -> List[Field]:
        return [
            Field("ntp_server",  "NTP Server IP",          "ip", validator=_ip,
                  hint="Primary NTP server"),
            Field("ntp_server2", "NTP Server 2 (optional)","ip", required=False,
                  validator=_ip, hint="Secondary NTP server"),
            Field("timezone",    "Timezone (optional)",    "text", required=False,
                  hint="e.g. UTC  or  EST -5 0  (Cisco format)"),
        ]

    def validate_against_config(self, inputs, running_config, vendor) -> List[str]:
        srv = inputs.get("ntp_server", "").strip()
        pat = rf"ntp-server\s+{re.escape(srv)}" if vendor == "Huawei" \
              else rf"ntp server\s+{re.escape(srv)}"
        if _exists_in_config(pat, running_config):
            return [f"NTP server {srv} already configured"]
        return []

    def generate_commands(self, inputs, vendor) -> List[str]:
        s1 = inputs["ntp_server"].strip()
        s2 = inputs.get("ntp_server2", "").strip()
        tz = inputs.get("timezone",    "").strip()
        pfx = "ntp-server" if vendor == "Huawei" else "ntp server"
        cmds = [f"{pfx} {s1}"]
        if s2:
            cmds.append(f"{pfx} {s2}")
        if tz:
            cmds.append(f"clock timezone {tz}")
        return cmds

    def generate_rollback(self, inputs, vendor) -> List[str]:
        s1  = inputs["ntp_server"].strip()
        pfx = "undo ntp-server" if vendor == "Huawei" else "no ntp server"
        return [f"{pfx} {s1}"]


class SnmpTask(ConfigTask):
    name        = "Configure SNMP"
    description = "Configure an SNMP community string and optional trap target."
    category    = "Monitoring"

    @property
    def fields(self) -> List[Field]:
        return [
            Field("community",    "Community String","text",    validator=_community,
                  hint="e.g. public  (1–32 alphanumeric chars)"),
            Field("permission",   "Permission",      "select",
                  options=["RO", "RW"], default="RO"),
            Field("snmp_version", "SNMP Version",    "select",
                  options=["2c", "3"],  default="2c"),
            Field("trap_host",    "Trap Host IP",    "ip",      required=False,
                  validator=_ip, hint="Optional SNMP trap destination"),
        ]

    def validate_against_config(self, inputs, running_config, vendor) -> List[str]:
        community = inputs.get("community", "").strip()
        pat = (rf"snmp-agent community\s+\S+\s+{re.escape(community)}"
               if vendor == "Huawei"
               else rf"snmp-server community\s+{re.escape(community)}")
        if _exists_in_config(pat, running_config):
            return [f"SNMP community '{community}' already exists"]
        return []

    def generate_commands(self, inputs, vendor) -> List[str]:
        community = inputs["community"].strip()
        perm      = inputs.get("permission",   "RO")
        ver       = inputs.get("snmp_version", "2c")
        trap      = inputs.get("trap_host",    "").strip()
        if vendor == "Huawei":
            rw = "read" if perm == "RO" else "write"
            cmds = ["snmp-agent",
                    f"snmp-agent sys-info version v{ver}",
                    f"snmp-agent community {rw} {community}"]
            if trap:
                cmds.append(f"snmp-agent target-host trap address udp-domain "
                            f"{trap} params securityname {community} v{ver}")
        else:
            cmds = [f"snmp-server community {community} {perm}",
                    f"snmp-server version {ver}"]
            if trap:
                cmds.append(f"snmp-server host {trap} traps version {ver} {community}")
        return cmds

    def generate_rollback(self, inputs, vendor) -> List[str]:
        community = inputs["community"].strip()
        perm = inputs.get("permission", "RO")
        if vendor == "Huawei":
            rw = "read" if perm == "RO" else "write"
            return [f"undo snmp-agent community {rw} {community}"]
        return [f"no snmp-server community {community}"]


# ── Routing tasks ─────────────────────────────────────────────────────────────

class StaticRouteTask(ConfigTask):
    name        = "Add Static Route"
    description = "Insert a static route into the routing table."
    category    = "Routing"

    @property
    def fields(self) -> List[Field]:
        return [
            Field("network",  "Destination Network", "text",
                  hint="e.g. 192.168.10.0"),
            Field("mask",     "Subnet Mask / Prefix", "text",
                  hint="e.g. 255.255.255.0  or  /24"),
            Field("next_hop", "Next Hop IP",          "ip",  validator=_ip),
            Field("distance", "Admin Distance",       "integer", required=False,
                  default="1", validator=_admin_distance, hint="1–255"),
        ]

    def validate_inputs(self, inputs) -> List[str]:
        errors = super().validate_inputs(inputs)
        net  = inputs.get("network", "").strip()
        mask = inputs.get("mask",    "").strip()
        if net and mask:
            try:
                cidr = mask if mask.startswith("/") else f"/{sum(bin(int(o)).count('1') for o in mask.split('.'))}"
                ipaddress.ip_network(f"{net}{cidr}", strict=False)
            except Exception:
                errors.append(f"[Network/Mask] '{net} {mask}' is not a valid network")
        return errors

    def validate_against_config(self, inputs, running_config, vendor) -> List[str]:
        net = inputs.get("network",  "").strip()
        nh  = inputs.get("next_hop", "").strip()
        pat = (rf"ip route-static {re.escape(net)}.*{re.escape(nh)}"
               if vendor == "Huawei"
               else rf"ip route {re.escape(net)}.*{re.escape(nh)}")
        if _exists_in_config(pat, running_config):
            return [f"Static route to {net} via {nh} already exists"]
        return []

    def _normalise_mask(self, mask: str) -> tuple:
        """Returns (dotted_mask, prefix_len) from either format."""
        if mask.startswith("/"):
            prefix = int(mask[1:])
            net    = ipaddress.ip_network(f"0.0.0.0/{prefix}", strict=False)
            return str(net.netmask), prefix
        octets = mask.split(".")
        prefix = sum(bin(int(o)).count("1") for o in octets)
        return mask, prefix

    def generate_commands(self, inputs, vendor) -> List[str]:
        net      = inputs["network"].strip()
        mask     = inputs["mask"].strip()
        nh       = inputs["next_hop"].strip()
        dist     = inputs.get("distance", "1").strip() or "1"
        dotted, prefix = self._normalise_mask(mask)
        if vendor == "Huawei":
            cmd = f"ip route-static {net} {prefix} {nh}"
            if dist != "1":
                cmd += f" preference {dist}"
        else:
            cmd = f"ip route {net} {dotted} {nh}"
            if dist != "1":
                cmd += f" {dist}"
        return [cmd]

    def generate_rollback(self, inputs, vendor) -> List[str]:
        net = inputs["network"].strip()
        mask = inputs["mask"].strip()
        nh  = inputs["next_hop"].strip()
        dotted, prefix = self._normalise_mask(mask)
        if vendor == "Huawei":
            return [f"undo ip route-static {net} {prefix} {nh}"]
        return [f"no ip route {net} {dotted} {nh}"]


# ── Registry ──────────────────────────────────────────────────────────────────

_ALL_TASKS: List[ConfigTask] = [
    BackupTask(),
    CreateVlanTask(),
    DeleteVlanTask(),
    AccessPortTask(),
    TrunkPortTask(),
    HostnameTask(),
    PortDescriptionTask(),
    InterfaceShutdownTask(),
    BannerTask(),
    SshEnableTask(),
    LdapTask(),
    NtpTask(),
    SnmpTask(),
    StaticRouteTask(),
]


def get_all_tasks() -> List[ConfigTask]:
    return _ALL_TASKS


def get_tasks_by_category() -> Dict[str, List[ConfigTask]]:
    categories: Dict[str, List[ConfigTask]] = {}
    for task in _ALL_TASKS:
        categories.setdefault(task.category, []).append(task)
    return categories


def get_task_by_name(name: str) -> Optional[ConfigTask]:
    return next((t for t in _ALL_TASKS if t.name == name), None)
