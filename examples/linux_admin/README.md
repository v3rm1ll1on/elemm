# 🛡️ Linux Guardian v2

Autonomous Linux administration and security auditing powered by the **Elemm v2 Protocol**.

## Overview
Linux Guardian provides a secure, landmark-based interface for managing Linux systems. It uses strictly namespaced tools to prevent command injection and ensure clear discovery.

## Landmarks
- **`system`**: Core management (hostname, uptime, bash execution).
- **`security`**: Auditing (user lists, network port scanning).
- **`logs`**: Forensic analysis (syslog/dmesg tailing).

## Usage

### 1. Launch the Server
```bash
# As MCP Server (Stdio)
PYTHONPATH=src python3 examples/linux_admin/guardian_v2.py

# As Web Gateway (FastAPI)
PYTHONPATH=src python3 examples/linux_admin/guardian_v2.py --fastapi
```

### 2. Example Sequence (Piping)
Find disk usage and system info in one turn:
```json
{
  "actions": [
    { "action": "system:get_info", "alias": "info" },
    { "action": "system:execute_bash", "parameters": { "command": "df -h" }, "alias": "disk" }
  ]
}
```

## Security Note
This is a demonstration. The `execute_bash` tool should be heavily restricted in production environments using a whitelist of allowed commands.
