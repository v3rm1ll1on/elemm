# 🪐 elemm (Landmark Protocol)

**The Bridge between Autonomous Agents and your API.**

`elemm` is a high-performance framework for FastAPI that transforms standard REST endpoints into "AI Landmarks". It enables autonomous agents (like Claude via MCP) to discover, understand, and navigate your API with zero-shot precision.

---

## ⚡ TL;DR: Quick Start

### 1. Install
```bash
pip install elemm
```

### 2. Decorate your FastAPI Routes
```python
from elemm import FastAPIProtocolManager
from fastapi import FastAPI, Header

app = FastAPI()
ai = FastAPIProtocolManager(agent_welcome="Welcome to System-X.")

@ai.landmark(id="get_status", type="read", description="Check system health.")
@app.get("/status")
async def health(auth: str = Header(..., description="API-Key")):
    return {"status": "nominal"}

# Register the protocol
app.include_router(ai.get_router())
ai.bind_to_app(app)
```

### 3. Done!
Your AI-readable manifest is now live at: `http://localhost:8000/.well-known/llm-landmarks.json`

---

## 🛡️ Enterprise-Ready Hardening

Unlike generic OpenAPI generators, `elemm` is built for **Safety and Precision**:

*   **Managed Parameters:** Sensitive headers (Authorization, API-Keys) are automatically marked as `managed_by: protocol`. The AI knows it shouldn't "hallucinate" these values.
*   **Context Injection:** Internal fields (FastAPI `Request`, `Session`) are automatically detected and moved to `context_dependencies`. They never clutter the AI's input schema.
*   **Strict Type Extraction:** Full support for Pydantic V2 Enums, Descriptions, and Examples.
*   **Discovery Debugging:** Detailed startup logs show exactly which landmarks were registered.
*   **Tags & Scaling:** Inherits FastAPI tags to categorize landmarks for large-scale APIs.

---

## 🚀 Use Cases: The Power of Landmarks

`elemm` is not just for shops. It’s for any system that needs an "AI interface":

### 🏠 1. Autonomous Smart Home
Register your IoT endpoints as landmarks.
*   **Action:** `set_temperature`, `toggle_lights`.
*   **Benefit:** A voice-agent can discover new smart devices in your home instantly via the manifest.

### 🏦 2. Financial Compliance & Ops
Turn complex banking APIs into navigable actions.
*   **Action:** `get_transaction_history`, `flag_fraudulent_activity`.
*   **Benefit:** AI auditors can follow "Landmark" instructions to perform 24/7 compliance checks.

### 🏥 3. Medical Data Pipelines
Expose patient data securely to diagnostic agents.
*   **Action:** `query_lab_results`.
*   **Benefit:** The `context_dependencies` ensure that PHI (Protected Health Information) is managed by the protocol/backend, not the LLM.

### 🎮 4. Dynamic Game Worlds
Let AI-NPCs interact with the world via REST.
*   **Action:** `open_vault_door`, `trade_item`.
*   **Benefit:** The manifest acts as the "Rulebook" for NPCs to interact logically with the game engine.

---

## 🔌 MCP & Claude Integration

Use the included `examples/mcp_bridge.py` to connect `elemm` to **Claude Desktop**.

Add this to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "my-ai-system": {
      "command": "python3",
      "args": ["/path/to/elemm/examples/mcp_bridge.py"],
      "env": { "LANDMARK_URLS": "http://localhost:8000" }
    }
  }
}
```

---

## 📜 Example Manifest (`llm-landmarks.json`)

```json
{
  "protocol": "elemm",
  "version": "2.5-autonomous",
  "actions": [
    {
      "id": "get_status",
      "type": "read",
      "description": "Check system health.",
      "method": "GET",
      "url": "/status",
      "parameters": [
        {
          "name": "auth",
          "description": "API-Key",
          "type": "string",
          "managed_by": "protocol"
        }
      ]
    }
  ]
}
```

---

## License
MIT License. Created by the AI Evolution Team.
