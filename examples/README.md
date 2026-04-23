# 🚀 Elemm Examples: Scaling AI Toolsets

Welcome to the official Elemm examples. This directory demonstrates how to transition from flat, overwhelming MCP tool-lists to a structured, hierarchical landmark architecture.

---

## 🏛️ [1. Enterprise Hub (Case Study)](./enterprise_hub)
**The "Token-Masterclass"**

This is our flagship example. It simulates a complex corporate environment (Solaris Hub) with **100+ tools** spread across different departments.
- **Problem**: In a flat MCP list, 100 tools would consume ~12k tokens per turn.
- **Elemm Solution**: Using landmarks, the agent only sees what's necessary, reducing consumption to **~2.8k tokens**.
- **Features**: Forensic audit simulation, autonomous navigation, and identity verification logic.

**Run it:**
```bash
python examples/enterprise_hub/server.py
```

---

## 🟢 [2. Basic Navigation](./basic_navigation)
**The "Hello World" of Landmarks**

A simplified version showing how to use the `@ai.landmark` and `@ai.action` decorators to structure a small API (Sales & Warehouse).
- **Auto-Discovery**: See how FastAPI tags automatically become navigation signposts.
- **Global Access**: Learn how to make specific tools visible across all landmarks.

**Run it:**
```bash
python examples/basic_navigation/server.py
```

---

## 🦾 [3. Synth-Genesis Bio-Shop](./synth_shop)
**The "Visual & Auth" Masterclass**

A high-fidelity E-commerce example in a Cyberpunk setting. It demonstrates how to handle complex agent behaviors and visual data.
- **Visual Priority**: Products include image URLs that the agent is instructed to render as Markdown images.
- **Security (JWT)**: Demonstrates a full authentication flow where the agent must login to access the cart and checkout.
- **Advanced Instructions**: Shows how to use `protocol_instructions` to force specific agent behaviors (e.g., proactive searching).

**Run it:**
```bash
python examples/synth_shop/server.py
```

---

## 🏢 [4. Office Management](./office_management)
**The "Service Automation" Example**

A practical example of workplace management. It shows how to handle bookings and location-based navigation.
- **Location Navigation**: Demonstrates how an agent can navigate through different cities to find offices.
- **CRUD Logic**: Shows full lifecycle management (List, Book, Cancel) of resources.
- **Business Logic**: Uses Pydantic models to ensure valid booking data (hours, dates).

**Run it:**
```bash
python examples/office_management/server.py
```

---

## 🛰️ [5. Elemm Gateway (The Broker)](../src/elemm_gateway)
**How to connect everything**

Elemm includes a built-in gateway (`elemm-connect`) that allows any MCP-compatible agent to browse an Elemm-powered site. 

**Usage:**
1. Start one of the example servers above.
2. Run `elemm-connect` in your terminal.
3. Point your agent (Claude Desktop, etc.) to the gateway.

---

## 📜 Legacy Archive
Older experiments and the original manual MCP bridge can be found in the [legacy/](./legacy) directory. We keep them for historical reference, but we recommend using the new Landmark + Gateway architecture for all new projects.
