# Elemm v1.0.0 Examples

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

## [Office Management](./office_management)
**Pydantic and Resource Lifecycle**
Practical resource management for modern workplaces:
- **Pydantic Integration**: Automatic schema generation for complex nested booking data.
- **Full Lifecycle**: Search, book, and cancel workflows within a structured landmark.

---

## [Linux Admin](./linux_admin)
**Infrastructure Management**
Tools for system-level monitoring and administration:
- **Safe Execution**: Wrapping system calls within a secure protocol boundary.
- **Technical Discovery**: Navigating complex infrastructure landmarks.

---

## [Basic Navigation](./basic_navigation)
**The Hello World**
The simplest starting point to understand the `@gateway.action` decorator and the three-stage protocol handshake.

---

## [MCP Configurations](./mcp_configs)
**Ready-to-use Agent Configs**
Copy-pasteable JSON templates for connecting your AI agent (e.g., Claude Desktop) to the Elemm Gateway:
- **[Windows (Native)](./mcp_configs/claude_desktop_windows.json)**
- **[WSL (Ubuntu/Debian)](./mcp_configs/claude_desktop_wsl.json)**
- **[Linux / macOS](./mcp_configs/claude_desktop_linux_mac.json)**

---

## Elemm Gateway (mcp_bridge.py)
**Connecting to Agents**
The `mcp_bridge.py` script acts as a broker between the Landmark Manifest Protocol and standard MCP-compatible agents like Claude Desktop.

**Quick Start:**
1. Start an example server (e.g., `python examples/smart_home/server.py`).
2. Point your agent to the bridge (see root README for configuration details).
3. Use the templates in `examples/mcp_configs/` for a quick setup.
4. Experience the performance and cost advantages of manifest-driven discovery.

---
*Maintained by Marc Stöcker.*
