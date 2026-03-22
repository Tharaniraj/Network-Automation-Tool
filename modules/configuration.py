"""
Configuration Management Module
Handles configuration deployment, backup, and restore
"""

import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from .logger import get_observability_manager


class ConfigurationManager:
    """Manages device configurations and deployments"""

    def __init__(self, config_dir: str = "configs", backup_dir: str = "backups"):
        self.config_dir = Path(config_dir)
        self.backup_dir = Path(backup_dir)
        self.config_dir.mkdir(exist_ok=True)
        self.backup_dir.mkdir(exist_ok=True)
        self.logger = get_observability_manager()
        self.config_index = self._load_index()

    def _load_index(self) -> Dict:
        """Load configuration index"""
        index_file = self.config_dir / "index.json"
        if index_file.exists():
            with open(index_file, 'r') as f:
                return json.load(f)
        return {"configurations": {}}

    def _save_index(self):
        """Save configuration index"""
        with open(self.config_dir / "index.json", 'w') as f:
            json.dump(self.config_index, f, indent=2)

    def backup_configuration(self, hostname: str, config_content: str,
                            config_type: str = "full") -> Tuple[bool, str]:
        """Backup device configuration"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{hostname}_{config_type}_{timestamp}.config"
            backup_path = self.backup_dir / backup_name
            
            with open(backup_path, 'w') as f:
                f.write(config_content)
            
            # Update index
            if hostname not in self.config_index["configurations"]:
                self.config_index["configurations"][hostname] = {"backups": []}
            
            self.config_index["configurations"][hostname]["backups"].append({
                "name": backup_name,
                "size": len(config_content),
                "timestamp": datetime.now().isoformat(),
                "type": config_type
            })
            self._save_index()
            
            self.logger.log_event(
                event_type="config_backup",
                device_name=hostname,
                description=f"Configuration backed up: {backup_name}",
                status="success",
                details={"size": len(config_content), "type": config_type}
            )
            
            return True, f"Configuration backed up: {backup_name}"
        
        except Exception as e:
            self.logger.log_error(hostname, str(e), "backup_error")
            return False, f"Backup failed: {str(e)}"

    def restore_configuration(self, hostname: str, backup_name: str) -> Tuple[bool, str, str]:
        """Restore device configuration from backup"""
        try:
            backup_path = self.backup_dir / backup_name
            
            if not backup_path.exists():
                return False, f"Backup not found: {backup_name}", ""
            
            with open(backup_path, 'r') as f:
                config_content = f.read()
            
            self.logger.log_event(
                event_type="config_restore",
                device_name=hostname,
                description=f"Configuration restored from: {backup_name}",
                status="success"
            )
            
            return True, f"Configuration restored successfully", config_content
        
        except Exception as e:
            self.logger.log_error(hostname, str(e), "restore_error")
            return False, f"Restore failed: {str(e)}", ""

    def save_configuration(self, hostname: str, config_content: str,
                          config_name: str = "current") -> Tuple[bool, str]:
        """Save configuration for a device"""
        try:
            config_file = self.config_dir / f"{hostname}_{config_name}.cfg"
            
            with open(config_file, 'w') as f:
                f.write(config_content)
            
            if hostname not in self.config_index["configurations"]:
                self.config_index["configurations"][hostname] = {"current": None, "backups": []}
            
            self.config_index["configurations"][hostname]["current"] = {
                "name": config_file.name,
                "size": len(config_content),
                "timestamp": datetime.now().isoformat()
            }
            self._save_index()
            
            self.logger.log_event(
                event_type="config_saved",
                device_name=hostname,
                description=f"Configuration saved: {config_file.name}",
                status="success"
            )
            
            return True, f"Configuration saved: {config_file.name}"
        
        except Exception as e:
            self.logger.log_error(hostname, str(e), "save_config_error")
            return False, f"Save failed: {str(e)}"

    def get_configuration(self, hostname: str, config_name: str = "current") -> Optional[str]:
        """Retrieve device configuration"""
        try:
            config_file = self.config_dir / f"{hostname}_{config_name}.cfg"
            
            if not config_file.exists():
                return None
            
            with open(config_file, 'r') as f:
                return f.read()
        
        except Exception as e:
            self.logger.log_error(hostname, str(e), "read_config_error")
            return None

    def compare_configurations(self, hostname: str, backup1: str,
                              backup2: str) -> Tuple[bool, str, Dict]:
        """Compare two configurations and show differences"""
        try:
            path1 = self.backup_dir / backup1
            path2 = self.backup_dir / backup2
            
            if not path1.exists() or not path2.exists():
                return False, "One or both backups not found", {}
            
            with open(path1, 'r') as f:
                config1 = f.readlines()
            with open(path2, 'r') as f:
                config2 = f.readlines()
            
            added_lines = [line for line in config2 if line not in config1]
            removed_lines = [line for line in config1 if line not in config2]
            
            differences = {
                "added": added_lines,
                "removed": removed_lines,
                "timestamp": datetime.now().isoformat()
            }
            
            self.logger.log_event(
                event_type="config_compare",
                device_name=hostname,
                description=f"Configuration comparison performed",
                status="success",
                details={"added_lines": len(added_lines), "removed_lines": len(removed_lines)}
            )
            
            return True, "Comparison completed", differences
        
        except Exception as e:
            self.logger.log_error(hostname, str(e), "compare_error")
            return False, f"Comparison failed: {str(e)}", {}

    def get_device_backups(self, hostname: str) -> List[Dict]:
        """Get all backups for a device"""
        return self.config_index["configurations"].get(hostname, {}).get("backups", [])

    def delete_backup(self, hostname: str, backup_name: str) -> Tuple[bool, str]:
        """Delete a backup"""
        try:
            backup_path = self.backup_dir / backup_name
            
            if not backup_path.exists():
                return False, f"Backup not found: {backup_name}"
            
            backup_path.unlink()
            
            # Remove from index
            if hostname in self.config_index["configurations"]:
                self.config_index["configurations"][hostname]["backups"] = [
                    b for b in self.config_index["configurations"][hostname]["backups"]
                    if b["name"] != backup_name
                ]
            self._save_index()
            
            self.logger.log_event(
                event_type="backup_deleted",
                device_name=hostname,
                description=f"Backup deleted: {backup_name}",
                status="success"
            )
            
            return True, f"Backup deleted: {backup_name}"
        
        except Exception as e:
            self.logger.log_error(hostname, str(e), "delete_backup_error")
            return False, f"Delete failed: {str(e)}"

    def export_configuration(self, hostname: str, format_type: str = "text") -> Tuple[bool, str]:
        """Export configuration in various formats"""
        try:
            config = self.get_configuration(hostname)
            if not config:
                return False, "Configuration not found"
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if format_type == "text":
                filename = f"{hostname}_config_{timestamp}.txt"
            elif format_type == "json":
                config = json.dumps({"hostname": hostname, "config": config}, indent=2)
                filename = f"{hostname}_config_{timestamp}.json"
            else:
                return False, f"Unsupported format: {format_type}"
            
            export_path = self.backup_dir / filename
            with open(export_path, 'w') as f:
                f.write(config)
            
            return True, f"Configuration exported: {filename}"
        
        except Exception as e:
            self.logger.log_error(hostname, str(e), "export_error")
            return False, f"Export failed: {str(e)}"
