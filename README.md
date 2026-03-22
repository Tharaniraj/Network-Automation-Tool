# Network Device Manager
## Automated Configuration & Observability for Cisco and Huawei Devices

**Version**: 1.0.0 | **Language**: Python 3.8+ | **GUI**: Tkinter

---

## 📌 Overview

**Network Device Manager** is a comprehensive, GUI-based solution for managing network devices without CLI complexity. It provides automated configuration, real-time status monitoring, and observability for Cisco and Huawei routers and switches.

### Key Features

✅ **Device Management**
- Add/remove devices from inventory
- Automatic device discovery (IP range scanning)
- Device grouping by type, vendor, or custom tags
- Multi-vendor support (Cisco, Huawei)

✅ **Configuration Automation**
- Backup device configurations
- Restore configurations from backups
- Compare configuration versions
- Deploy configurations
- Configuration versioning and audit trail

✅ **Real-Time Monitoring**
- Live device status (online/offline/degraded)
- CPU and memory usage tracking
- Device health scoring
- Health trend analysis
- Alert system with severity levels

✅ **Observability & Telemetry**
- Event logging system
- Metrics collection
- Configuration change tracking
- Audit trail for all operations
- Performance analytics

✅ **Compliance Checking**
- Pre-configured compliance rules for Cisco and Huawei
- Custom rule creation
- Compliance scoring
- Configuration evidence generation
- Audit reports

---

## 🏗️ Architecture

```
Network-Device-Manager/
├── main.py                     # Main GUI application
├── modules/
│   ├── __init__.py
│   ├── device_manager.py       # Device inventory & discovery
│   ├── configuration.py        # Config backup/restore/deploy
│   ├── status_monitor.py       # Real-time status & alerts
│   ├── compliance.py           # Compliance checking
│   └── logger.py               # Logging & observability
├── data/
│   ├── devices.json            # Device inventory
│   ├── compliance_rules.json   # Compliance rules
│   └── index.json              # Configuration index
├── configs/                    # Device configurations
├── backups/                    # Configuration backups
├── logs/                       # Application logs
│   ├── device_manager_*.log    # Timestamped logs
│   ├── events.json             # Event log
│   └── telemetry.json          # Metrics
└── reports/                    # Generated reports
```

---

## 📦 Installation

### Requirements
- Python 3.8 or higher
- Tkinter (usually included with Python)
- No external dependencies

### Setup

```bash
# Clone or download the project
cd Network-Device-Manager

# Run the application
python main.py
```

---

## 🚀 Quick Start

### 1. Add Your First Device

1. Launch the application
2. Go to **Device** menu → **Add Device**
3. Fill in details:
   - **Hostname**: device-name
   - **IP Address**: 192.168.1.1
   - **Device Type**: cisco_router (or cisco_switch/huawei_router/huawei_switch)
   - **Username**: admin
   - **Password**: password
   - **Port**: 22 (default)
   - **SNMP Community**: public (optional)

4. Click "Add Device"

### 2. Discover Devices

1. Go to **Device** menu → **Discover Devices**
2. Enter network range:
   - Format: `192.168.1.0/24` or `192.168.1.1-10`
3. Provide credentials and device type
4. Click "Discover"

### 3. Backup Configuration

1. Select device in **Inventory** tab
2. Go to **Configuration** tab → **Backup**
3. Configuration is automatically backed up with timestamp

### 4. Monitor Device Status

1. Go to **Monitoring** tab
2. Select device from dropdown
3. Click "Update Status"
4. View real-time metrics (CPU, Memory, Health)

### 5. Check Compliance

1. Go to **Compliance** tab
2. Select device or run check on highlighted device
3. Review compliance status and score
4. Generate audit report

---

## 📊 Dashboard

The **Dashboard** tab provides overview statistics:
- Total devices in inventory
- Online/offline count
- Per-vendor device count
- Average device health
- Active alerts
- Overall compliance score

---

## 🔧 Module Reference

### Device Manager (`device_manager.py`)

Manages device inventory and discovery.

**Key Methods:**
```python
device_manager.add_device(hostname, ip, device_type, username, password)
device_manager.remove_device(hostname)
device_manager.get_all_devices()
device_manager.discover_devices(network, username, password, device_type)
device_manager.get_inventory_stats()
```

### Configuration Manager (`configuration.py`)

Handles configuration operations.

**Key Methods:**
```python
config_manager.backup_configuration(hostname, config_content)
config_manager.restore_configuration(hostname, backup_name)
config_manager.save_configuration(hostname, config_content)
config_manager.get_configuration(hostname)
config_manager.compare_configurations(hostname, backup1, backup2)
```

### Status Monitor (`status_monitor.py`)

Real-time monitoring and alerting.

**Key Methods:**
```python
status_monitor.update_device_status(hostname, status, health, cpu, memory, uptime)
status_monitor.get_device_status(hostname)
status_monitor.get_active_alerts(hostname)
status_monitor.generate_status_report()
```

### Compliance Checker (`compliance.py`)

Configuration compliance validation.

**Key Methods:**
```python
compliance_checker.check_device_compliance(hostname, vendor, config)
compliance_checker.add_custom_rule(vendor, rule_name, pattern)
compliance_checker.get_compliance_report()
compliance_checker.generate_compliance_evidence(hostname)
```

### Observability Manager (`logger.py`)

Logging and telemetry.

**Key Methods:**
```python
logger.log_event(event_type, device_name, description, status)
logger.log_metric(device_name, metric_name, value, unit)
logger.log_error(device_name, error_msg, error_type)
logger.get_device_events(device_name)
logger.get_device_metrics(device_name)
```

---

## 📝 Data Files

### devices.json
```json
{
  "device-name": {
    "hostname": "device-name",
    "ip_address": "192.168.1.1",
    "device_type": "cisco_router",
    "vendor": "Cisco",
    "os": "Cisco IOS/IOS-XE",
    "username": "admin",
    "password": "encrypted",
    "port": 22,
    "snmp_community": "public",
    "tags": ["production", "core"],
    "status": "online",
    "last_checked": "2025-03-22T10:30:00",
    "enabled": true
  }
}
```

### compliance_rules.json
```json
{
  "cisco": {
    "ssh_enabled": {
      "pattern": "ip ssh version 2",
      "required": true
    },
    "logging_enabled": {
      "pattern": "logging",
      "required": true
    }
  },
  "huawei": {
    "ssh_enabled": {
      "pattern": "stelnet server enable",
      "required": true
    }
  }
}
```

---

## 📊 Supported Device Types

| Type | Vendor | OS | Description |
|------|--------|----|----|
| `cisco_router` | Cisco | IOS/IOS-XE | Cisco routing devices |
| `cisco_switch` | Cisco | IOS/IOS-XE | Cisco switching devices |
| `huawei_router` | Huawei | VRP | Huawei routing devices |
| `huawei_switch` | Huawei | VRP | Huawei switching devices |

---

## 📈 Monitoring & Alerts

### Health Scoring

Devices receive a health score (0-100) based on:
- Connectivity status
- CPU utilization
- Memory utilization
- Configuration compliance
- Response time

### Alert Thresholds

- **CPU > 80%**: Medium severity warning
- **Memory > 85%**: Medium severity warning
- **Health Score < 50%**: High severity alert
- **Device Offline**: Critical severity alert

### Alert Management

1. View active alerts in Dashboard
2. Acknowledge alerts to clear notifications
3. Review alert history in Logs tab

---

## 🔒 Security Considerations

1. **Credentials**: Store securely, consider environment variables for production
2. **Access Control**: Implement authentication per deployment requirements
3. **Audit Trail**: All operations logged in `logs/events.json`
4. **Backups**: Configuration backups stored in `backups/` directory
5. **Encryption**: Implement TLS for device connections in production

---

## 📊 Reporting

### Available Reports

1. **Status Report**: Current device status overview
2. **Compliance Report**: Compliance check results
3. **Configuration History**: Backup and change history
4. **Alert Summary**: Recent alerts and trends

### Export Formats

- JSON (detailed data)
- Text (readable format)
- Custom formats (extensible)

---

## 🔌 Device Connection

### SSH Connection Details
- Default port: 22
- Supports username/password authentication
- Keys stored in device inventory

### SNMP
- Community string configuration
- Metrics collection support

---

## 🛠️ Customization

### Adding Custom Compliance Rules

```python
from modules.compliance import ComplianceChecker

checker = ComplianceChecker()
checker.add_custom_rule("cisco", "ntp_configured", "ntp server", required=True)
```

### Custom Device Tags

```python
from modules.device_manager import DeviceManager

dm = DeviceManager()
dm.update_device("device-1", tags=["production", "critical", "monitored"])
```

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| Cannot connect to device | Check IP, credentials, firewall rules |
| GUI not launching | Ensure Tkinter is installed: `pip install tk` |
| Device discovery timeout | Increase network range, check network connectivity |
| Configuration backup fails | Check write permissions in `backups/` directory |

---

## 📚 File Structure

```
logs/
├── device_manager_YYYYMMDD.log   # Application logs with timestamp
├── events.json                    # All events in JSON format
└── telemetry.json                 # Metrics collection

data/
├── devices.json                   # Device inventory
├── compliance_rules.json          # Compliance rule definitions
└── index.json                     # Configuration index

backups/
└── hostname_full_YYYYMMDD_HHMMSS.config  # Configuration backups

configs/
├── hostname_current.cfg           # Latest configuration
├── hostname_index.json            # Config version index
└── [backups linked here]

reports/
└── compliance_report_YYYYMMDD_HHMMSS.json  # Generated reports
```

---

## 🚀 Advanced Features

### Device Discovery
Automatic scanning of IP ranges to find and register devices automatically.

### Configuration Versioning
Every backup creates a timestamped version with full change tracking.

### Real-time Dashboards
Monitor multiple devices simultaneously with live updates.

### Bulk Operations
Perform operations on multiple devices at once.

### Custom Rules
Create organization-specific compliance rules.

---

## 📄 License

Network Device Manager v1.0.0 - Production Ready

---

## 🤝 Support

For issues or feature requests, refer to the logs in `logs/` directory for detailed error information.

---

## 🎯 Next Steps

1. **Add Devices**: Start by adding your network devices
2. **Configure Backups**: Set up regular backup schedules
3. **Establish Rules**: Define compliance rules for your organization
4. **Monitor**: Enable real-time monitoring
5. **Report**: Generate compliance and status reports

---

## 🔄 Version History

- **v1.0.0** (March 2025): Initial release with full feature set
  - Device management and discovery
  - Configuration automation
  - Real-time monitoring
  - Compliance checking
  - Observability framework
  - Dashboard and reporting

---

**Created**: March 2025  
**Status**: ✅ Production Ready
