# Elemm Examples: From Classic to Landmark 🚀

This directory showcases the architectural shift from manual MCP tool-mapping to the **Elemm Landmark Protocol**.

---

## 🟢 [1. Navigation & Scaling Demo](./navigation_demo)
**The "Context Hygiene" Masterclass**

This demo shows how to scale an API to hundreds of tools without drowning the AI.
- **Hierarchical Discovery**: Explore how tags like `Market & Sales` automatically become navigation signposts.
- **Agent-Repair-Kit**: Try sending invalid data (e.g., amount=500) and watch how Elemm guides the agent back with specific `remedy` instructions.
- **Sanitization**: See how special characters in tags are safely converted to IDs.

**Run it:**
```bash
python examples/navigation_demo/api.py
```

---

## 🟢 [2. Elemm MCP Implementation](./elemm_mcp)
**The Zero-Maintenance AI Bridge**

Compare this to the `classic_mcp` (if still present in your view) to see why Elemm is superior.
- **Auto-Discovery**: The MCP bridge dynamically fetches the `llm-landmarks.json`.
- **Embedded Logic**: Instructions and remedies are part of the tool metadata, not the system prompt.
- **Pydantic Power**: Watch how deep nested models and Enums are extracted for the agent.

**Run it:**
```bash
python examples/elemm_mcp/api.py
```

---

## 🛠️ MCP Bridge Implementation
The file `mcp_bridge.py` in this directory is a **generic, production-ready bridge**. You can use it to connect *any* Elemm-powered API to Claude Desktop or Cursor.

### Integration with Claude Desktop
Add this to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "enterprise-ai": {
      "command": "python3",
      "args": ["/absolute/path/to/mcp_bridge.py"],
      "env": {
        "LANDMARK_URLS": "http://localhost:8000"
      }
    }
  }
}
```

---

## 📄 Summary of Advantages
| Feature | Manual MCP | **Elemm (Landmarks)** |
| :--- | :--- | :--- |
| **Maintenance** | High (Sync required) | **Zero (Auto-detect)** |
| **Token Cost** | factor 1x | **factor < 0.1x** |
| **Resilience** | Low (Raw errors) | **High (Self-healing)** |
| **Scale** | ~30-50 tools | **Unlimited** |
