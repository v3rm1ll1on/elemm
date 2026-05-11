# Getting Started with Elemm

Welcome to Elemm! This guide will help you set up your first autonomous tool environment using the Landmark Manifest Protocol.

---

## 1. Installation

Install Elemm directly from PyPI:

```bash
pip install elemm
```

### 1.1 Virtual Environment & Path Management (Recommended)

To keep your system clean and avoid dependency conflicts, use a virtual environment:

```bash
# 1. Create a virtual environment
python3 -m venv .venv

# 2. Activate it
# Linux/macOS/WSL:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

# 3. Install the package
pip install elemm
```

#### Locating the Executable
AI agents often require absolute paths to the `elemm-gateway` executable. You can find it by running:
- **Linux/macOS/WSL**: `which elemm-gateway`
- **Windows**: `where elemm-gateway`

Typical paths:
- **Linux/macOS**: `/home/user/.local/bin/elemm-gateway` or inside your venv: `/path/to/project/.venv/bin/elemm-gateway`
- **WSL**: `/home/user/project/.venv/bin/elemm-gateway`
- **Windows**: `C:\Users\User\AppData\Local\Programs\Python\Python310\Scripts\elemm-gateway.exe`

---

## 2. Option A: Use the Gateway (Fastest)

The **Elemm Gateway** is a universal MCP server that connects to any OpenAPI, GraphQL, or native Elemm API. No code required.

Because it uses the STDIO transport by default, **you do not run it directly in your terminal**. Instead, you configure your MCP client to start it.

### Platform-Specific MCP Configuration

AI agents like Claude Desktop or Cursor require a JSON configuration to start the gateway via STDIO. Use the example that matches your operating system.

#### Windows (Native)
File: `%APPDATA%\Claude\claude_desktop_config.json`
```json
{
  "mcpServers": {
    "elemm-gateway": {
      "command": "C:\\Users\\<USER>\\project\\.venv\\Scripts\\python.exe",
      "args": ["-m", "elemm_gateway.cli"]
    }
  }
}
```

#### WSL (Ubuntu/Debian)
If your project lives in WSL but you run the AI agent on Windows:
File: `%APPDATA%\Claude\claude_desktop_config.json`
```json
{
  "mcpServers": {
    "elemm-gateway": {
      "command": "wsl.exe",
      "args": [
        "-d", "Ubuntu",
        "-u", "<USER>",
        "bash", "-c",
        "cd /home/<USER>/project && ./.venv/bin/python3 -m elemm_gateway.cli"
      ]
    }
  }
}
```

#### Linux / macOS
File: `~/.config/Claude/claude_desktop_config.json` (Linux) or `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)
```json
{
  "mcpServers": {
    "elemm-gateway": {
      "command": "/path/to/project/.venv/bin/python3",
      "args": ["-m", "elemm_gateway.cli"]
    }
  }
}
```

*(Note: Always prefer absolute paths to both the python executable and the project directory).*

Then start Claude and tell your agent: 
> *"Use Elemm to connect to https://petstore.swagger.io/v2/swagger.json and list all available pets."*

> [!TIP]
> See the [Gateway Reference](GATEWAY.md) for the complete documentation on security policies, authentication vault, sequence engine, and more.

---

## 2. Option B: Build Your Own Landmark Server

If you want to expose your own Python functions as Elemm landmarks, use the decorator-based approach:

```python
from elemm import AIProtocolManager, MetadataRegistry

registry = MetadataRegistry("landmarks.yaml")
manager = AIProtocolManager(registry=registry)

@manager.landmark("lighting:set_brightness")
async def set_brightness(room: str, level: int):
    """Sets the brightness level (0-100) for a specific room."""
    return {"room": room, "brightness": level, "status": "adjusted"}
```

---

## 3. How Agents Interact with Elemm

When an agent connects to an Elemm service (via the Gateway or a native server), it follows a strict discovery protocol:

1.  **Connect**: The agent calls `connect_to_site(url)` to establish a connection.
2.  **Get Manifest**: The agent calls `get_manifest()` to receive the protocol rules and a topology of available landmarks. This step authorizes the session.
3.  **Discover**: The agent calls `get_landmarks()` to see high-level functional areas.
4.  **Inspect**: The agent calls `inspect_landmark(landmark_id)` to get the exact technical signatures (parameters, types, descriptions) for the tools it needs.
5.  **Execute**: Only after inspection, the agent uses `call_action()` for single calls or `execute_sequence()` for multi-step pipelines with data piping.

---

## 4. Next Steps

*   **[Gateway Reference](GATEWAY.md)**: Full documentation for the Elemm Gateway (OpenAPI, GraphQL, Security, Vault, Sequences).
*   **[Developer Guide](DEVELOPER_GUIDE.md)**: Learn about Pydantic integration and SmartRepair.
*   **[Architecture Overview](ARCHITECTURE.md)**: Understand the "Landmark" philosophy.
*   **[Benchmarking Results](BENCHMARKING.md)**: See performance comparisons.
