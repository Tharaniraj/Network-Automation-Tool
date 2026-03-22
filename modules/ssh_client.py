"""
SSH client module for real device connectivity via netmiko.
Provides graceful fallback messaging when netmiko is not installed.
"""

from typing import Tuple, List

try:
    from netmiko import ConnectHandler
    from netmiko.exceptions import (
        NetMikoTimeoutException,
        NetMikoAuthenticationException,
    )
    NETMIKO_AVAILABLE = True
except ImportError:
    NETMIKO_AVAILABLE = False

# Maps internal device_type keys to netmiko driver names
DEVICE_TYPE_MAP = {
    "cisco_router": "cisco_ios",
    "cisco_switch": "cisco_ios",
    "huawei_router": "huawei",
    "huawei_switch": "huawei",
}

_NOT_INSTALLED_MSG = (
    "netmiko is not installed. Install it with: pip install netmiko"
)


def _build_conn_params(device: dict, timeout: int = 30) -> dict:
    """Build netmiko connection parameter dict from a device record."""
    device_type = DEVICE_TYPE_MAP.get(device.get("device_type", ""), "cisco_ios")
    return {
        "device_type": device_type,
        "host": device["ip_address"],
        "username": device["username"],
        "password": device["password"],
        "port": device.get("port", 22),
        "timeout": timeout,
        "session_timeout": timeout * 2,
        "conn_timeout": timeout,
    }


def test_connectivity(device: dict) -> Tuple[bool, str]:
    """
    Test SSH reachability to a device.

    Returns (success, message).
    """
    if not NETMIKO_AVAILABLE:
        return False, _NOT_INSTALLED_MSG

    try:
        with ConnectHandler(**_build_conn_params(device, timeout=10)) as conn:
            prompt = conn.find_prompt()
        return True, f"Connected — prompt: {prompt}"
    except NetMikoTimeoutException:
        return False, f"Connection timed out ({device['ip_address']})"
    except NetMikoAuthenticationException:
        return False, f"Authentication failed ({device['ip_address']})"
    except Exception as exc:
        return False, f"SSH error: {exc}"


def get_running_config(device: dict) -> Tuple[bool, str]:
    """
    Retrieve the running configuration from a device via SSH.

    Returns (success, config_text_or_error_message).
    """
    if not NETMIKO_AVAILABLE:
        return False, _NOT_INSTALLED_MSG

    try:
        with ConnectHandler(**_build_conn_params(device)) as conn:
            if device.get("vendor", "").lower() == "huawei":
                output = conn.send_command("display current-configuration")
            else:
                output = conn.send_command(
                    "show running-config", read_timeout=60
                )
        return True, output
    except NetMikoTimeoutException:
        return False, f"Connection timed out ({device['ip_address']})"
    except NetMikoAuthenticationException:
        return False, f"Authentication failed ({device['ip_address']})"
    except Exception as exc:
        return False, f"SSH error: {exc}"


def push_config(device: dict, config_lines: List[str]) -> Tuple[bool, str]:
    """
    Push configuration commands to a device via SSH.
    The config is saved/committed after sending.

    Returns (success, output_or_error_message).
    """
    if not NETMIKO_AVAILABLE:
        return False, _NOT_INSTALLED_MSG

    try:
        with ConnectHandler(**_build_conn_params(device)) as conn:
            output = conn.send_config_set(config_lines)
            conn.save_config()
        return True, output
    except NetMikoTimeoutException:
        return False, f"Connection timed out ({device['ip_address']})"
    except NetMikoAuthenticationException:
        return False, f"Authentication failed ({device['ip_address']})"
    except Exception as exc:
        return False, f"SSH error: {exc}"
