# Quick Start Guide - Network Device Manager

## 60-Second Setup

### 1. Launch Application
```bash
python main.py
```

### 2. Add Your First Device
- **Menu**: Device → Add Device
- **Hostname**: cisco-router-01
- **IP**: 192.168.1.1
- **Type**: cisco_router
- **Username**: admin
- **Password**: yourpassword

### 3. View Dashboard
- Open **Dashboard** tab
- Click "Refresh Dashboard"
- See inventory statistics

### 4. Backup Configuration
- Go to **Configuration** tab
- Select device
- Click **Backup**
- Configuration saved with timestamp

### 5. Monitor Status
- Go to **Monitoring** tab
- Select device
- Click "Update Status"
- View real-time metrics

---

## Common Tasks

### Add Multiple Devices
1. Device → Discover Devices
2. Enter network range: 192.168.1.0/24
3. Provide credentials
4. Select device type
5. Found devices appear in Inventory

### Browse Configuration History
1. Configuration tab
2. Select device
3. Click "View"
4. Backups listed with timestamps

### Check Compliance
1. Compliance tab
2. Select device
3. Click "Check Compliance"
4. Review pass/fail status
5. Generate audit report with "Generate Report"

### View All Events
1. Logs tab
2. All events displayed with timestamps
3. Device operations tracked
<br>
---

## Keyboard Shortcuts

- **Ctrl+B**: Backup config
- **Ctrl+R**: Refresh
- **Ctrl+E**: Export

---

## Need Help?

Check `logs/device_manager_*.log` for detailed error messages.
