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

AI agents like Claude Desktop or Cursor require a JSON configuration to start the gateway. **The easiest way to generate this is using the built-in Config Generator:**

```bash
elemm-gateway cfg-gen
```

This interactive tool will automatically detect your operating system, paths, and WSL environment, and generate a ready-to-use JSON block like this:

```json
{
  "mcpServers": {
    "elemm-gateway": {
      "command": "/path/to/project/.venv/bin/elemm-gateway",
      "args": ["--transport", "stdio"]
    }
  }
}
```

Copy the generated output and place it in your client's config file:
- **Windows / WSL:** `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

Then start Claude and tell your agent: 
> *"Use Elemm to connect to https://petstore.swagger.io/v2/swagger.json and list all available pets."*

> [!TIP]
> See the [Gateway Reference](GATEWAY.md) for the complete documentation on security policies, authentication vault, sequence engine, and more.

---

## 2. Option B: Run in Docker (2-Step Setup, Recommended for Cloud & Dev)

Running Elemm inside Docker is the cleanest way to run the entire stack. With a single command, you start both the **Visual Dashboard** (on port `8090`) and the **MCP Gateway** (on port `8000` via SSE).

This eliminates virtual environments, path resolution issues, and OS-specific setup.

### Step 1: Run the Docker Container

You can start Elemm either using a simple `docker run` command or with `docker compose`.

#### Option A: Using the Docker CLI
```bash
docker run -d \
  -p 8000:8000 \
  -p 8090:8090 \
  -v ~/.elemm:/root/.elemm \
  --name elemm-gateway \
  ghcr.io/v3rm1ll1on/elemm:latest
```

#### Option B: Using Docker Compose (Recommended)
Download the [docker-compose.yml](../examples/docker-compose.yml) example file and start the stack with:

```bash
docker compose up -d
```

> [!NOTE]
> Mounting the `~/.elemm` volume ensures your **Security Policies** and **Credential Vault** are securely persisted on your host machine.

### Step 2: Configure Claude Desktop (SSE Connection)

Since the container runs in its own network space, configure Claude Desktop to connect via **Server-Sent Events (SSE)** instead of standard input/output (STDIO).

Add this block to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "elemm-gateway": {
      "type": "sse",
      "url": "http://localhost:8000/sse"
    }
  }
}
```

*File Locations for `claude_desktop_config.json`:*
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS / Linux:** `~/Library/Application Support/Claude/claude_desktop_config.json`

An example configuration file is available at [claude_desktop_sse_config.json](../examples/claude_desktop_sse_config.json).

### Step 3: Access the Visual Dashboard

Open your browser and navigate to:
👉 **[http://localhost:8090](http://localhost:8090)**

From here, you can watch real-time telemetry, manage your secure credential vault, and inspect active session topologies.

---

## 3. Option C: Build Your Own Landmark Server

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

## 4. How Agents Interact with Elemm

When an agent connects to an Elemm service (via the Gateway or a native server), it follows a strict discovery protocol:

1.  **Connect**: The agent calls `connect_to_site(url)` to establish a connection.
2.  **Get Manifest**: The agent calls `get_manifest()` to receive the protocol rules and a topology of available landmarks. This step authorizes the session.
3.  **Discover**: The agent calls `get_landmarks()` to see high-level functional areas.
4.  **Inspect**: The agent calls `inspect_landmark(landmark_id)` to get the exact technical signatures (parameters, types, descriptions) for the tools it needs.
5.  **Execute**: Only after inspection, the agent uses `call_action()` for single calls or `execute_sequence()` for multi-step pipelines with data piping.

---

## 5. Next Steps

*   **[Gateway Reference](GATEWAY.md)**: Full documentation for the Elemm Gateway (OpenAPI, GraphQL, Security, Vault, Sequences).
*   **[Developer Guide](DEVELOPER_GUIDE.md)**: Learn about Pydantic integration and SmartRepair.
*   **[Architecture Overview](ARCHITECTURE.md)**: Understand the "Landmark" philosophy.
*   **[Benchmarking Results](BENCHMARKING.md)**: See performance comparisons.
