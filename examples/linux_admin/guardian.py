"""
Elemm Example: Linux System Guardian (Native MCP)
-------------------------------------------------
This example demonstrates how to use Elemm as a framework-agnostic library 
to build a powerful, hierarchical system administration tool without FastAPI.

Usage:
  PYTHONPATH=src python examples/linux_admin/guardian.py
"""

import os
import subprocess
import platform
import shutil
import re
import logging
from typing import List, Dict, Optional, Any
from elemm.core.manager import BaseAIProtocolManager
from elemm.core.exceptions import ActionError

# Configure logging to stderr for MCP compatibility
logging.basicConfig(level=logging.INFO, stream=os.sys.stderr)
logger = logging.getLogger("linux-guardian")

manager = BaseAIProtocolManager(
    agent_welcome="Linux System Guardian (Live)",
    agent_instructions="You are a system administration agent. Monitor and manage the host safely."
)

def run_cmd(cmd: List[str]) -> str:
    try:
        return subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode('utf-8')
    except Exception as e:
        logger.error(f"Command failed: {cmd} - {e}")
        return f"Error: {str(e)}"

# --- LANDMARK: CPU & HARDWARE ---

@manager.tool(id="get_cpu_usage", groups=["cpu_info"])
def get_cpu_usage():
    """Returns load averages and core count."""
    try:
        with open('/proc/loadavg', 'r') as f:
            load = f.read().split()
        return {"load_1m": float(load[0]), "load_5m": float(load[1]), "load_15m": float(load[2]), "cores": os.cpu_count()}
    except Exception as e:
        return {"error": str(e)}

@manager.tool(id="get_cpu_details", groups=["cpu_info"])
def get_cpu_details():
    """Returns detailed CPU architecture info using lscpu."""
    out = run_cmd(["lscpu"])
    return {line.split(":")[0].strip(): line.split(":")[1].strip() for line in out.splitlines() if ":" in line}

@manager.tool(id="get_cpu_temp", groups=["cpu_info"])
def get_cpu_temp():
    """Reads thermal sensors from /sys/class/thermal."""
    temps = {}
    try:
        if not os.path.exists('/sys/class/thermal'):
            return {"status": "unsupported", "message": "Thermal sensors not found."}
        for zone in os.listdir('/sys/class/thermal'):
            if zone.startswith('thermal_zone'):
                with open(f'/sys/class/thermal/{zone}/type', 'r') as f:
                    type_ = f.read().strip()
                with open(f'/sys/class/thermal/{zone}/temp', 'r') as f:
                    temp = int(f.read().strip()) / 1000.0
                temps[type_] = temp
    except Exception as e:
        return {"error": str(e)}
    return temps

# --- LANDMARK: MEMORY ---

@manager.tool(id="get_mem_info", groups=["memory"])
def get_mem_info():
    """Returns RAM stats in MB parsed from /proc/meminfo."""
    meminfo = {}
    try:
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                parts = line.split(':')
                if len(parts) == 2:
                    meminfo[parts[0].strip()] = int(parts[1].split()[0].strip()) // 1024
        return {
            "total_mb": meminfo.get("MemTotal"),
            "available_mb": meminfo.get("MemAvailable"),
            "free_mb": meminfo.get("MemFree")
        }
    except Exception as e:
        return {"error": str(e)}

# --- LANDMARK: STORAGE ---

@manager.tool(id="get_disk_usage", groups=["storage"])
def get_disk_usage(path: str = "/"):
    """Check disk usage for a specific path."""
    try:
        usage = shutil.disk_usage(path)
        return {
            "path": path,
            "total_gb": usage.total >> 30,
            "used_gb": usage.used >> 30,
            "free_gb": usage.free >> 30,
            "percent": round((usage.used / usage.total) * 100, 1)
        }
    except Exception as e:
        raise ActionError(f"Path '{path}' invalid or inaccessible.", remedy="Provide a valid absolute path.")

@manager.tool(id="list_block_devices", groups=["storage"])
def list_block_devices():
    """Lists block devices using lsblk."""
    return {"devices": run_cmd(["lsblk", "-o", "NAME,SIZE,TYPE,MOUNTPOINT"]).splitlines()}

@manager.tool(id="get_mounts", groups=["storage"])
def get_mounts():
    """Returns currently mounted filesystems."""
    return {"mounts": run_cmd(["mount"]).splitlines()}

# --- LANDMARK: NETWORK ---

@manager.tool(id="get_ip_addr", groups=["network"])
def get_ips():
    """Returns local network interfaces and IP addresses."""
    return {"interfaces": run_cmd(["ip", "-o", "addr"]).splitlines()}

@manager.tool(id="get_ss_stats", groups=["network"])
def get_ss():
    """Returns active listening ports (TCP/UDP)."""
    return {"listening": run_cmd(["ss", "-tunlp"]).splitlines()}

@manager.tool(id="ping_host", groups=["network"])
def ping_host(host: str, count: int = 2):
    """Pings a remote host to verify connectivity."""
    if not re.match(r"^[a-zA-Z0-9.-]+$", host):
        raise ActionError("Invalid hostname format.", remedy="Use a valid IP or domain name.")
    return {"output": run_cmd(["ping", "-c", str(count), host])}

# --- LANDMARK: PROCESSES ---

@manager.tool(id="list_procs", groups=["processes"])
def list_procs():
    """Returns top processes by CPU usage."""
    return {"top_processes": run_cmd(["ps", "-eo", "pid,ppid,cmd,%cpu,%mem", "--sort=-%cpu"]).splitlines()[:15]}

@manager.tool(id="get_kernel_info", groups=["processes"])
def get_kernel_info():
    """Returns kernel release and version info."""
    return {
        "release": platform.release(),
        "version": platform.version(),
        "node": platform.node()
    }

@manager.tool(id="get_uptime", groups=["processes"])
def get_uptime():
    """Returns system uptime."""
    return {"uptime": run_cmd(["uptime"]).strip()}

# --- LANDMARK CONFIGURATION ---

manager.navigation_landmarks = [
    {"id": "cpu_info", "notes": "Monitor CPU architecture, load and temperature."},
    {"id": "memory", "notes": "Track RAM and virtual memory usage."},
    {"id": "storage", "notes": "Manage disks, partitions and mount points."},
    {"id": "network", "notes": "Inspect interfaces and active network connections."},
    {"id": "processes", "notes": "Monitor running processes and system state."}
]

if __name__ == "__main__":
    from elemm.mcp.bridge import LandmarkBridge
    # Create the bridge and run as a Stdio MCP server
    bridge = LandmarkBridge(manager=manager, server_name="linux-guardian")
    bridge.run_stdio()
