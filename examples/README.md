# Elemm v1.2.0 Examples

Welcome to the official Elemm examples. This directory demonstrates how to build autonomous, reliable, and efficient toolsets using the Landmark Manifest Protocol.

---

## [Smart Home](./smart_home)
**The Validation and Repair Showcase**
The primary demonstration of the Landmark Manifest Protocol. It highlights:
- **Strict Typing**: Using `Literal` and `Enum` for precise agent control.
- **SmartRepair**: Real-world examples of guiding an agent through validation errors.
- **Sequencing**: Demonstrating multi-step execution (e.g., security and lighting) in a single turn.

---

## [Synth-Genesis Bio-Shop](./synth_shop)
**Stateful E-Commerce Simulation**
A cyberpunk e-commerce environment demonstrating:
- **Stateful Actions**: Cart management and complex checkout flows.
- **Security**: Autonomous handling of session-based authentication.
- **Rich Metadata**: Using detailed landmark descriptions for high-fidelity reasoning.

---

## [Linux Admin](./linux_admin)
**Infrastructure Management**
Tools for system-level monitoring and administration:
- **Safe Execution**: Wrapping system calls within a secure protocol boundary.
- **Technical Discovery**: Navigating complex infrastructure landmarks.

---

## [MCP Configurations](./mcp_configs)
**Ready-to-use Agent Configs**
Copy-pasteable JSON templates for connecting your AI agent (e.g., Claude Desktop) to the Elemm Gateway:
- **[Windows (Native)](./mcp_configs/claude_desktop_windows.json)**
- **[WSL (Ubuntu/Debian)](./mcp_configs/claude_desktop_wsl.json)**
- **[Linux / macOS](./mcp_configs/claude_desktop_linux_mac.json)**
- **[WSL (Bridge Mode 🔌)](./mcp_configs/claude_desktop_bridge_mode.json)** - Tunnel stdio to remote/local SSE Gateway
- **[Docker (Bridge Mode 🔌)](./mcp_configs/claude_desktop_bridge_docker.json)** - Containerized stdio-to-SSE tunnel

---

## Elemm Gateway
**Connecting to Agents**

The **Elemm Gateway** is a protocol-aware broker that connects any AI agent to your Landmark servers.

**Quick Start:**

### Option A: Fully Containerized Orchestration (The Pro Way 🚀)
You can boot up the entire Elemm ecosystem—the SSE Gateway, the Live Dashboard, and all three example servers—at the same time with a single command!

1. Navigate to the examples directory:
   ```bash
   cd examples
   ```
2. Start the Docker Compose orchestration:
   ```bash
   docker compose up -d
   ```
This maps all ports automatically:
* **Gateway (SSE):** `http://localhost:8000/sse`
* **Dashboard (UI):** `http://localhost:8090`
* **Smart Home:** `http://localhost:8002`
* **Linux Guardian:** `http://localhost:8003`
* **Synth Shop:** `http://localhost:8004`

### Option B: Local Execution (Native)
1. Start an example server (e.g., `python smart_home/smarthome_v2.py`).
2. Run the Gateway: `elemm-gateway http://localhost:8002` (or use the configurations in `examples/mcp_configs/`).
3. Experience the performance and cost advantages of manifest-driven discovery.

> [!TIP]
> Use the minimalist `examples/mcp.py` as a template for your own custom MCP bridge scripts.

---
*Maintained by Marc Stöcker.*
