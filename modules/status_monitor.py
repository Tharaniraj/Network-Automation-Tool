"""
Status Monitoring Module
Real-time device status and health monitoring
"""

import json
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum
from .logger import get_observability_manager


class DeviceStatus(Enum):
    """Device status states"""
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    ERROR = "error"
    UNKNOWN = "unknown"


class StatusMonitor:
    """Monitors real-time device status and health"""

    def __init__(self):
        self.logger = get_observability_manager()
        self.device_status = {}
        self.alerts = []

    def update_device_status(self, hostname: str, status: DeviceStatus,
                            health_score: int = 100, cpu: float = 0,
                            memory: float = 0, uptime: str = "unknown") -> Dict:
        """Update device status and metrics"""
        try:
            # Validate health score
            health_score = max(0, min(100, health_score))
            
            status_data = {
                "hostname": hostname,
                "status": status.value,
                "health_score": health_score,
                "cpu_usage": cpu,
                "memory_usage": memory,
                "uptime": uptime,
                "last_updated": datetime.now().isoformat(),
                "timestamp": datetime.now().timestamp()
            }
            
            self.device_status[hostname] = status_data
            
            # Check for alerts
            self._check_alerts(hostname, status_data)
            
            # Log metrics
            self.logger.log_metric(hostname, "health_score", health_score, "%")
            self.logger.log_metric(hostname, "cpu_usage", cpu, "%")
            self.logger.log_metric(hostname, "memory_usage", memory, "%")
            
            return status_data
        
        except Exception as e:
            self.logger.log_error(hostname, str(e), "status_update_error")
            return {}

    def _check_alerts(self, hostname: str, status_data: Dict):
        """Check for alert conditions"""
        alerts_triggered = []
        
        # CPU usage alert
        if status_data["cpu_usage"] > 80:
            alert = self._create_alert(hostname, "cpu_high", 
                                      f"CPU usage high: {status_data['cpu_usage']}%")
            alerts_triggered.append(alert)
        
        # Memory alert
        if status_data["memory_usage"] > 85:
            alert = self._create_alert(hostname, "memory_high",
                                      f"Memory usage high: {status_data['memory_usage']}%")
            alerts_triggered.append(alert)
        
        # Health score alert
        if status_data["health_score"] < 50:
            alert = self._create_alert(hostname, "health_degraded",
                                      f"Health score degraded: {status_data['health_score']}%")
            alerts_triggered.append(alert)
        
        # Device offline alert
        if status_data["status"] == "offline":
            alert = self._create_alert(hostname, "device_offline",
                                      f"Device {hostname} is offline")
            alerts_triggered.append(alert)
        
        self.alerts.extend(alerts_triggered)

    def _create_alert(self, hostname: str, alert_type: str, message: str) -> Dict:
        """Create an alert"""
        alert = {
            "hostname": hostname,
            "type": alert_type,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "severity": "high" if alert_type == "device_offline" else "medium",
            "acknowledged": False
        }
        
        self.logger.log_event(
            event_type="alert_triggered",
            device_name=hostname,
            description=message,
            status="alert"
        )
        
        return alert

    def get_device_status(self, hostname: str) -> Optional[Dict]:
        """Get current status of a device"""
        return self.device_status.get(hostname)

    def get_all_statuses(self) -> Dict[str, Dict]:
        """Get status of all devices"""
        return self.device_status

    def get_device_health(self, hostname: str) -> Dict:
        """Get detailed health information"""
        status = self.device_status.get(hostname)
        if not status:
            return {"error": "Device not found"}
        
        health_info = {
            "hostname": hostname,
            "overall_health": status["health_score"],
            "components": {
                "cpu": {
                    "status": "warning" if status["cpu_usage"] > 80 else "healthy",
                    "usage": status["cpu_usage"]
                },
                "memory": {
                    "status": "warning" if status["memory_usage"] > 85 else "healthy",
                    "usage": status["memory_usage"]
                },
                "connectivity": {
                    "status": status["status"],
                    "uptime": status["uptime"]
                }
            },
            "last_updated": status["last_updated"]
        }
        
        return health_info

    def get_active_alerts(self, hostname: Optional[str] = None) -> List[Dict]:
        """Get active (unacknowledged) alerts"""
        alerts = [a for a in self.alerts if not a["acknowledged"]]
        if hostname:
            alerts = [a for a in alerts if a["hostname"] == hostname]
        return alerts

    def acknowledge_alert(self, alert_index: int) -> bool:
        """Acknowledge an alert"""
        if 0 <= alert_index < len(self.alerts):
            self.alerts[alert_index]["acknowledged"] = True
            self.logger.log_event(
                event_type="alert_acknowledged",
                device_name=self.alerts[alert_index]["hostname"],
                description=f"Alert acknowledged: {self.alerts[alert_index]['type']}",
                status="info"
            )
            return True
        return False

    def get_alert_summary(self) -> Dict:
        """Get alert summary statistics"""
        active = len(self.get_active_alerts())
        total = len(self.alerts)
        
        by_type = {}
        for alert in self.alerts:
            alert_type = alert["type"]
            by_type[alert_type] = by_type.get(alert_type, 0) + 1
        
        return {
            "active_alerts": active,
            "total_alerts": total,
            "by_type": by_type,
            "last_updated": datetime.now().isoformat()
        }

    def get_health_trend(self, hostname: str, hours: int = 24) -> List[Dict]:
        """Get health trend data for graphs"""
        # This would need persistent storage in production
        # For now, return sample data structure
        return [
            {
                "timestamp": datetime.now().isoformat(),
                "health_score": 100,
                "cpu": 45,
                "memory": 60
            }
        ]

    def generate_status_report(self) -> Dict:
        """Generate status report for all devices"""
        report = {
            "generated": datetime.now().isoformat(),
            "total_devices": len(self.device_status),
            "online_devices": len([d for d in self.device_status.values() 
                                  if d["status"] == "online"]),
            "offline_devices": len([d for d in self.device_status.values()
                                   if d["status"] == "offline"]),
            "avg_health": sum(d["health_score"] for d in self.device_status.values()) / 
                         max(1, len(self.device_status)),
            "active_alerts": len(self.get_active_alerts()),
            "devices": {}
        }
        
        for hostname, status in self.device_status.items():
            report["devices"][hostname] = {
                "status": status["status"],
                "health": status["health_score"],
                "cpu": status["cpu_usage"],
                "memory": status["memory_usage"]
            }
        
        return report
