# 🚀 Elemm v1.0.0 Examples

Welcome to the official Elemm examples. This directory demonstrates how to build autonomous, reliable, and efficient toolsets using the Elemm protocol.

---

## 🏠 [Smart Home](./smart_home)
**The "Validation & Repair" Showcase**
This is the primary example for Elemm v1.0.0. It demonstrates:
- **Strict Typing**: Using `Literal` and `Enum` for precise AI control.
- **SmartRepair**: How to guide an agent when it uses a wrong `room_id`.
- **Sequencing**: Arming security and turning off lights in one turn.

---

## 🤖 [Synth-Genesis Bio-Shop](./synth_shop)
**The "Auth & State" Example**
A cyberpunk e-commerce simulation.
- **Stateful Actions**: Cart management and checkout flows.
- **Security**: Demonstrates how agents handle authentication requirements.
- **Complex Metadata**: Rich descriptions for high-fidelity reasoning.

---

## 🏢 [Office Management](./office_management)
**The "Pydantic & CRUD" Example**
Practical resource management for modern workplaces.
- **Pydantic Integration**: Automatic schema generation for complex booking data.
- **Resource Lifecycle**: List, search, book, and cancel workflows.

---

## 🐧 [Linux Admin](./linux_admin)
**The "System-Level" Showcase**
Tools for infrastructure management and monitoring.
- **Safe Execution**: Demonstrates how to wrap system calls securely.
- **Discovery**: Navigating through technical system landmarks.

---

## 🟢 [Basic Navigation](./basic_navigation)
**The "Hello World"**
A simple starting point to understand the `@manager.landmark` decorator and the 3-stage discovery handshake.

---

## 🛰️ Elemm Gateway (mcp.py)
**Connecting to the AI World**
The easiest way to use these examples is the `mcp.py` script in this directory.

**Quick Start:**
1. Start an example (e.g., `python examples/smart_home/server.py`).
2. Point your agent to `examples/mcp.py` (see main README for details).
3. Observe the massive token savings compared to standard tool-calling!

---
*Maintained by Marc Stöcker.*
