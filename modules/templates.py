"""
Configuration Templates Module
Pre-built templates for different network devices
"""

TEMPLATES = {
    "cisco_router_basic": {
        "name": "Cisco Router - Basic Setup",
        "vendor": "Cisco",
        "device_type": "cisco_router",
        "category": "Basic",
        "template": """! Cisco Router - Basic Configuration Template
! Generated for Network Device Manager

version 15.0
no service pad
service timestamps debug datetime msec
service timestamps log datetime msec
service password-encryption
!
hostname router-1
!
enable password 7 [ENCRYPTED_PASSWORD]
enable secret 5 [ENCRYPTED_SECRET]
!
! Console and VTY Lines
line con 0
 exec-timeout 15 0
 logging synchronous
!
line vty 0 4
 exec-timeout 15 0
 transport input ssh
 logging synchronous
!
! SSH Configuration - REQUIRED
ip ssh version 2
ip ssh logging events
ip ssh timeout 120
ip ssh authentication-retries 3
!
! DNS Configuration - REQUIRED
ip domain-name company.local
ip name-server 8.8.8.8
ip name-server 8.8.4.4
!
! NTP Configuration - REQUIRED
ntp server 10.0.0.1
ntp server 10.0.0.2
ntp update-calendar
!
! Logging Configuration - REQUIRED
logging on
logging host 10.0.0.50
logging level debug
!
! SNMP Configuration - REQUIRED
snmp-server community public RO
snmp-server community private RW
snmp-server contact admin@company.com
snmp-server location "Production Network"
!
! Interface Configuration
interface GigabitEthernet0/0/0
 description WAN Interface
 ip address 203.0.113.1 255.255.255.0
 no shutdown
!
interface GigabitEthernet0/0/1
 description LAN Interface
 ip address 192.168.1.1 255.255.255.0
 no shutdown
!
! Routing Configuration
ip route 0.0.0.0 0.0.0.0 203.0.113.254
!
! ACL for Management
access-list 100 permit tcp 192.168.1.0 0.0.0.255 any eq ssh
access-list 100 deny tcp any any eq ssh
!
! Banner
banner motd ^CC
=================================================================
WARNING: Unauthorized access to this device is forbidden and will
be prosecuted by law. By accessing this device, you agree that
your actions may be monitored and recorded.
^C
!
end
"""
    },
    
    "cisco_router_advanced": {
        "name": "Cisco Router - Advanced Setup",
        "vendor": "Cisco",
        "device_type": "cisco_router",
        "category": "Advanced",
        "template": """! Cisco Router - Advanced Configuration Template

version 15.0
service timestamps debug datetime msec
service timestamps log datetime msec
service password-encryption
!
hostname router-core
!
! AAA Configuration
aaa new-model
aaa authentication login default local
aaa authorization exec default local
!
! Enable Password
enable secret 5 [ENCRYPTED_SECRET]
!
! SSH Configuration
ip ssh version 2
ip ssh logging events
ip ssh timeout 180
!
! DNS and Domain
ip domain-name company.com
ip name-server 8.8.8.8
ip name-server 8.8.4.4
!
! NTP with Authentication
ntp authenticate
ntp authentication-key 1 md5 [NTP_KEY] 7
ntp trusted-key 1
ntp server 10.0.0.1 key 1 prefer
ntp server 10.0.0.2 key 1
!
! Logging Configuration
logging on
logging host 10.0.0.50
logging source-interface GigabitEthernet0/0/1
logging buffered 32768 informational
logging console informational
!
! SNMP Configuration
snmp-server engineID local 8000070904[YOUR_ENGINEID]
snmp-server community public RO
snmp-server community private RW
snmp-server contact "Network Admin"
snmp-server location "Data Center"
!
! Interface Configuration - WAN
interface GigabitEthernet0/0/0
 description WAN to ISP
 ip address 203.0.113.1 255.255.255.0
 ip access-group 100 in
 no shutdown
!
! Interface Configuration - LAN
interface GigabitEthernet0/0/1
 description LAN Segment
 ip address 192.168.1.1 255.255.255.0
 ip helper-address 10.0.0.5
 no shutdown
!
! Access Control Lists
access-list 100 permit tcp 192.168.1.0 0.0.0.255 any eq ssh
access-list 100 permit icmp any any
access-list 100 deny tcp any any eq telnet
access-list 100 deny tcp any any eq ssh
!
! OSPF Configuration
router ospf 1
 network 192.168.1.0 0.0.0.255 area 0
 network 10.0.0.0 0.0.255.255 area 0
 passive-interface GigabitEthernet0/0/1
!
! BGP Configuration (if needed)
! router bgp 65000
!  bgp log-neighbor-changes
!  neighbor 203.0.113.254 remote-as 65001
!  address-family ipv4
!   network 192.168.0.0 mask 255.255.0.0
!   neighbor 203.0.113.254 activate
!
end
"""
    },
    
    "cisco_switch_basic": {
        "name": "Cisco Switch - Basic Setup",
        "vendor": "Cisco",
        "device_type": "cisco_switch",
        "category": "Basic",
        "template": """! Cisco Switch - Basic Configuration Template

version 15.0
service timestamps debug datetime msec
service timestamps log datetime msec
service password-encryption
!
hostname switch-1
!
enable secret 5 [ENCRYPTED_SECRET]
!
! Spanning Tree Protocol
spanning-tree mode rapid-pvst
spanning-tree portfast bpduguard default
!
! VLAN Configuration
vlan 1
 name Management
!
vlan 10
 name Data
!
vlan 20
 name Voice
!
vlan 30
 name Video
!
! Management Interface
interface Vlan1
 ip address 192.168.100.1 255.255.255.0
 no shutdown
!
! SSH Configuration
ip ssh version 2
ip ssh logging events
!
! DNS Configuration
ip name-server 8.8.8.8
ip name-server 8.8.4.4
!
! NTP Configuration
ntp server 10.0.0.1
ntp server 10.0.0.2
!
! Logging
logging on
logging host 10.0.0.50
!
! SNMP
snmp-server community public RO
snmp-server community private RW
snmp-server contact admin@company.com
snmp-server location "Building A"
!
! Access Ports
interface range GigabitEthernet1/0/1 - 24
 switchport access vlan 10
 switchport mode access
 spanning-tree portfast
 no shutdown
!
! Trunk Port to other switch
interface GigabitEthernet 1/0/49
 switchport mode trunk
 switchport trunk allowed vlan 1,10,20,30
 spanning-tree link-type point-to-point
 no shutdown
!
! Line Configuration
line con 0
 exec-timeout 15 0
!
line vty 0 4
 transport input ssh
 exec-timeout 15 0
!
end
"""
    },
    
    "huawei_router_basic": {
        "name": "Huawei Router - Basic Setup",
        "vendor": "Huawei",
        "device_type": "huawei_router",
        "category": "Basic",
        "template": """# Huawei Router - Basic Configuration Template
# Generated for Network Device Manager

sysName router-huawei-1
#
# System configuration
system-config
#
# DNS Configuration - REQUIRED
dns server 8.8.8.8
dns server 8.8.4.4
#
# NTP Configuration - REQUIRED
ntp-server 10.0.0.1 123
ntp-server 10.0.0.2 123
#
# SNMP Configuration - REQUIRED
snmp-agent community read public
snmp-agent community write private
snmp-agent sys-info contact admin@company.com
snmp-agent sys-info location "Data Center"
#
# Logging Configuration - REQUIRED
logging server 10.0.0.50
info-center loghost 10.0.0.50
info-center enable trap
#
# SSH/Stelnet Configuration - REQUIRED
stelnet server enable
ssh server enable
ssh server port 22
#
# User management
aaa
 authentication-scheme default
 authorization-scheme default
 accounting-scheme default
 domain default
#
# Interface configuration
interface Ethernet 1/0/0
 description WAN Interface
 ip address 203.0.113.1 255.255.255.0
 mtu 1500
 no shutdown
#
interface Ethernet 1/0/1
 description LAN Interface
 ip address 192.168.1.1 255.255.255.0
 no shutdown
#
# Static routes
ip route-static 0.0.0.0 0.0.0.0 203.0.113.254
#
# Access control
acl 2100
 rule 1 permit source 192.168.1.0 0.0.0.255
 rule 5 deny source any
#
# VRP System banner
header login information "Welcome to Huawei Router"
#
# Line VTY configuration
line vty 0 4
 authentication-mode password
 set authentication password cipher default123456
 user privilege level 15
 terminal databits 8
#
end
#
"""
    },
    
    "huawei_switch_basic": {
        "name": "Huawei Switch - Basic Setup",
        "vendor": "Huawei",
        "device_type": "huawei_switch",
        "category": "Basic",
        "template": """# Huawei Switch - Basic Configuration Template

sysName switch-huawei-1
#
# DNS Configuration - REQUIRED
dns server 8.8.8.8
dns server 8.8.4.4
#
# NTP Configuration - REQUIRED
ntp-server 10.0.0.1 123
ntp-server 10.0.0.2 123
#
# SNMP Configuration - REQUIRED
snmp-agent community read public
snmp-agent community write private
snmp-agent sys-info contact admin@company.com
snmp-agent sys-info location "Building A"
#
# Logging Configuration - REQUIRED
logging server 10.0.0.50
info-center loghost 10.0.0.50
#
# SSH/Stelnet Configuration - REQUIRED
stelnet server enable
ssh server enable
#
# VLAN Configuration
vlan batch 1 2 10 20 30
#
vlan 1
 name Management
#
vlan 10
 name Data
#
vlan 20
 name Voice
#
vlan 30
 name Video
#
# Management Interface
interface Vlanif 1
 ip address 192.168.100.1 255.255.255.0
#
# Access Ports
interface Ethernet 1/0/1
 port link-type access
 port default vlan 10
 description "Access Port 1"
#
interface Ethernet 1/0/2
 port link-type access
 port default vlan 20
 description "Access Port 2"
#
# Trunk Port
interface Ethernet 1/0/49
 port link-type trunk
 port trunk allow-pass vlan 1 10 20 30
 description "Uplink Port"
#
# STP Configuration
stp mode mstp
stp enable
#
# Line VTY Configuration
line vty 0 4
 authentication-mode password
 set authentication password cipher default123456
 user privilege level 15
#
header login information "Welcome to Huawei Switch"
#
end
#
"""
    },

    "cisco_firewall_basic": {
        "name": "Cisco ASA Firewall - Basic",
        "vendor": "Cisco",
        "device_type": "cisco_router",
        "category": "Firewall",
        "template": """! Cisco ASA Firewall - Basic Configuration Template

: Saved
:
ASA Version 9.x
!
hostname asa-firewall-1
domain-name company.com
enable password [ENCRYPTED_PASSWORD]
!
! DNS Configuration
dns domain-lookup inside
dns domain-lookup outside
dns server-group DefaultDNS
 name-server 8.8.8.8
 name-server 8.8.4.4
!
! NTP Configuration
ntp server 10.0.0.1 prefer
ntp server 10.0.0.2
!
! SNMP Configuration
snmp-server community public
snmp-server enable traps
!
! Interface Configuration
interface GigabitEthernet1/1
 nameif outside
 security-level 0
 ip address 203.0.113.1 255.255.255.0
 no shutdown
!
interface GigabitEthernet1/2
 nameif inside
 security-level 100
 ip address 192.168.1.1 255.255.255.0
 no shutdown
!
! Default Route
route outside 0.0.0.0 0.0.0.0 203.0.113.254 1
!
! NAT Configuration
object network obj-192.168
 subnet 192.168.1.0 255.255.255.0
!
object-group network DM_INLINE_NETWORK_1
 network-object object obj-192.168
!
nat (inside,outside) 1 source dynamic DM_INLINE_NETWORK_1 interface
!
! Access Rules
access-list inside_access_in extended permit tcp any any eq 443
access-list inside_access_in extended permit tcp any any eq 80
access-list inside_access_in extended deny ip any any
!
access-group inside_access_in in interface inside
!
! Username
username admin privilege 15 password [ENCRYPTED_PASSWORD]
!
! HTTP Server
http server enable
http 0.0.0.0 0.0.0.0 inside
!
! AAA Configuration
aaa authentication ssh console LOCAL
!
end
"""
    },

    "juniper_srx_basic": {
        "name": "Juniper SRX - Basic Setup",
        "vendor": "Juniper",
        "device_type": "cisco_router",
        "category": "Firewall",
        "template": """# Juniper SRX Firewall - Basic Configuration

system {
    host-name srx-firewall-1;
    domain-name company.com;
    time-zone America/New_York;
}

# DNS Configuration
system {
    name-server 8.8.8.8;
    name-server 8.8.4.4;
}

# NTP Configuration
system {
    ntp {
        server 10.0.0.1;
        server 10.0.0.2;
    }
}

# SNMP Configuration
snmp {
    community public {
        authorization read-only;
    }
    community private {
        authorization read-write;
    }
    trap-group trap1 {
        targets {
            10.0.0.50;
        }
    }
}

# Syslog Configuration
syslog {
    host 10.0.0.50 {
        interactive-commands none;
        any emergency;
    }
}

# Interface Configuration
interfaces {
    ge-0/0/0 {
        description "WAN Interface";
        unit 0 {
            family inet {
                address 203.0.113.1/24;
            }
        }
    }
    ge-0/0/1 {
        description "LAN Interface";
        unit 0 {
            family inet {
                address 192.168.1.1/24;
            }
        }
    }
}

# Routing
routing-options {
    static {
        route 0.0.0.0/0 next-hop 203.0.113.254;
    }
}

# Zones
security {
    zones {
        security-zone untrust {
            host-inbound-traffic {
                system-services {
                    dns;
                    ssh;
                }
            }
            interfaces {
                ge-0/0/0 {
                    host-inbound-traffic {
                        system-services {
                            ssh;
                        }
                    }
                }
            }
        }
        security-zone trust {
            interfaces {
                ge-0/0/1;
            }
        }
    }
}

# Security Policies
security {
    policies {
        from-zone trust to-zone untrust {
            policy allow-outbound {
                match {
                    source-address any;
                    destination-address any;
                    application any;
                }
                then {
                    permit;
                }
            }
        }
        from-zone untrust to-zone trust {
            policy allow-inbound {
                match {
                    source-address any;
                    destination-address any;
                    application any;
                }
                then {
                    permit;
                }
            }
        }
    }
}

# Apply configuration
commit
"""
    }
}


def get_all_templates() -> dict:
    """Get all available templates"""
    return TEMPLATES


def get_templates_by_vendor(vendor: str) -> dict:
    """Get templates for specific vendor"""
    return {k: v for k, v in TEMPLATES.items() if v["vendor"].lower() == vendor.lower()}


def get_templates_by_category(category: str) -> dict:
    """Get templates by category"""
    return {k: v for k, v in TEMPLATES.items() if v["category"] == category}


def get_template_content(template_key: str) -> str:
    """Get template content by key"""
    if template_key in TEMPLATES:
        return TEMPLATES[template_key]["template"]
    return ""


def get_template_name(template_key: str) -> str:
    """Get template display name"""
    if template_key in TEMPLATES:
        return TEMPLATES[template_key]["name"]
    return ""


def get_categories() -> list:
    """Get all available categories"""
    return sorted(list(set(t["category"] for t in TEMPLATES.values())))


def get_vendors() -> list:
    """Get all available vendors"""
    return sorted(list(set(t["vendor"] for t in TEMPLATES.values())))
