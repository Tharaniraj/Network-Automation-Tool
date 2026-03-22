"""
Observability and Logging Module
Handles telemetry, event logging, and monitoring data
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional


class ObservabilityManager:
    """Manages logging, telemetry, and observability data"""

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Setup logging
        log_file = self.log_dir / f"device_manager_{datetime.now().strftime('%Y%m%d')}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger("NetworkDeviceManager")
        
        # Telemetry storage
        self.telemetry_file = self.log_dir / "telemetry.json"
        self.events_file = self.log_dir / "events.json"
        self._init_telemetry_files()

    def _init_telemetry_files(self):
        """Initialize telemetry and events JSON files"""
        if not self.telemetry_file.exists():
            with open(self.telemetry_file, 'w') as f:
                json.dump({"metrics": []}, f)
        
        if not self.events_file.exists():
            with open(self.events_file, 'w') as f:
                json.dump({"events": []}, f)

    def log_event(self, event_type: str, device_name: Optional[str], 
                  description: str, status: str = "info", details: Dict = None):
        """Log an event with timestamp and metadata"""
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "device": device_name,
            "description": description,
            "status": status,
            "details": details or {}
        }
        
        self.logger.info(f"[{event_type}] {device_name}: {description}")
        self._append_to_file(self.events_file, "events", event)
        return event

    def log_metric(self, device_name: str, metric_name: str, 
                   value: Any, unit: str = "", tags: Dict = None):
        """Log a telemetry metric"""
        metric = {
            "timestamp": datetime.now().isoformat(),
            "device": device_name,
            "metric": metric_name,
            "value": value,
            "unit": unit,
            "tags": tags or {}
        }
        
        self._append_to_file(self.telemetry_file, "metrics", metric)
        return metric

    def log_configuration_change(self, device_name: str, change_type: str,
                                 before: str, after: str, user: str = "system"):
        """Log configuration changes for audit trail"""
        change_event = {
            "timestamp": datetime.now().isoformat(),
            "device": device_name,
            "type": f"config_{change_type}",
            "before": before[:500],  # Truncate large configs
            "after": after[:500],
            "user": user,
            "status": "success"
        }
        
        self.logger.info(f"Configuration change on {device_name}: {change_type}")
        self._append_to_file(self.events_file, "events", change_event)
        return change_event

    def log_error(self, device_name: Optional[str], error_msg: str, 
                  error_type: str = "error", traceback_info: str = ""):
        """Log errors and exceptions"""
        error_event = {
            "timestamp": datetime.now().isoformat(),
            "device": device_name,
            "error_type": error_type,
            "message": error_msg,
            "traceback": traceback_info
        }
        
        self.logger.error(f"[{error_type}] {device_name}: {error_msg}")
        self._append_to_file(self.events_file, "events", error_event)
        return error_event

    def _append_to_file(self, file_path: Path, key: str, data: Dict):
        """Append data to JSON file safely"""
        try:
            with open(file_path, 'r+') as f:
                content = json.load(f)
                content[key].append(data)
                f.seek(0)
                json.dump(content, f, indent=2)
                f.truncate()
        except Exception as e:
            self.logger.error(f"Failed to append to {file_path}: {e}")

    def get_device_events(self, device_name: str, limit: int = 100) -> List[Dict]:
        """Get recent events for a specific device"""
        try:
            with open(self.events_file, 'r') as f:
                data = json.load(f)
                device_events = [e for e in data["events"] if e.get("device") == device_name]
                return device_events[-limit:]
        except Exception as e:
            self.logger.error(f"Failed to get device events: {e}")
            return []

    def get_device_metrics(self, device_name: str, limit: int = 100) -> List[Dict]:
        """Get recent metrics for a specific device"""
        try:
            with open(self.telemetry_file, 'r') as f:
                data = json.load(f)
                device_metrics = [m for m in data["metrics"] if m.get("device") == device_name]
                return device_metrics[-limit:]
        except Exception as e:
            self.logger.error(f"Failed to get device metrics: {e}")
            return []

    def get_summary_stats(self) -> Dict:
        """Get summary statistics for dashboard"""
        try:
            with open(self.events_file, 'r') as f:
                events = json.load(f)["events"]
            
            error_count = len([e for e in events if e.get("status") == "error"])
            config_changes = len([e for e in events if "config_" in e.get("type", "")])
            
            return {
                "total_events": len(events),
                "errors": error_count,
                "config_changes": config_changes,
                "last_updated": datetime.now().isoformat()
            }
        except Exception as e:
            self.logger.error(f"Failed to get summary stats: {e}")
            return {}


# Global instance
_observability_manager: Optional[ObservabilityManager] = None


def get_observability_manager() -> ObservabilityManager:
    """Get or create global observability manager"""
    global _observability_manager
    if _observability_manager is None:
        _observability_manager = ObservabilityManager()
    return _observability_manager
