"""
Package initialization
"""

__version__ = "1.0.0"
__author__ = "Network Device Manager Team"
__description__ = "Automated configuration and observability for Cisco and Huawei devices"

from .device_manager import DeviceManager
from .configuration import ConfigurationManager
from .status_monitor import StatusMonitor, DeviceStatus
from .compliance import ComplianceChecker
from .logger import get_observability_manager

__all__ = [
    "DeviceManager",
    "ConfigurationManager",
    "StatusMonitor",
    "DeviceStatus",
    "ComplianceChecker",
    "get_observability_manager"
]
