# elemm vs. Classic MCP: Technical Comparison

This directory showcases the architectural differences between manual MCP tool-mapping and the **elemm Landmark Protocol** using the "Nexus-Corp Resource API" as a real-world scenario.

---

## 🔴 [Classic MCP Implementation](./classic_mcp)
**The Manual Mapping Approach**

In this scenario, the API is "unaware" of the AI. The developer must build and maintain a separate MCP server that acts as a hardcoded translator.

*   **Schema Replication**: Every Pydantic model (`Resource`, `Location`, `Status`) must be manually recreated as a JSON Schema in the MCP server.
*   **High Coupling**: Any change in the API (e.g., adding a field or changing a constraint) requires a synchronized update in the MCP server code, or the tools will break.
*   **External Logic (Prop Eng)**: Business rules and error-handling instructions (e.g., *"Only set OFFLINE during maintenance"*) must be fed to the LLM via large System Prompts, consuming significant context tokens.

---

## 🟢 [elemm MCP Implementation](./elemm_mcp)
**The Landmark Protocol Approach**

The API is "AI-native" and describes itself via the Landmark manifest. The MCP bridge is purely generic and requires zero knowledge of the underlying business logic.

*   **Auto-Discovery**: The bridge dynamically fetches the `llm-landmarks.json` manifest. Schemas, Enums, and field descriptions are extracted automatically from the FastAPI code.
*   **Zero-Maintenance Bridge**: You can add dozens of new endpoints or complex models to the API; the `mcp_server.py` remains static and never needs to be touched.
*   **Embedded Logic**: Instructions (`remedy`, `instructions`, `type`) are part of the tool metadata. The LLM receives guidance exactly when it inspects the tool, eliminating the need for bloated System Prompts.

---

### File Structure
1.  **`api.py`**: The core service. Compare how Landmarks are defined inline vs. ignored.
2.  **`mcp_server.py`**: The bridge. Notice the ~150 lines of boilerplate in the classic version vs. the generic logic in the elemm version.
3.  **`client_demo.py`**: The execution layer. Watch how the classic version requires a manual `SYSTEM_PROMPT` to function reliably.

---

## 🧪 Testing & Validation

These examples are fully functional but require an LLM environment to see them in action. 

### Local Testing with Ollama
1.  **Install Ollama** and pull a model: `ollama run gemma4:latest`.
2.  **Start the API**: `python examples/elemm_mcp/api.py`.
3.  **Run the demo**: `python examples/elemm_mcp/client_demo.py`.

The `client_demo.py` acts as a minimal agent that talks to the MCP bridge. You can use it to verify that your landmarks are correctly discovered and executed.

> [!NOTE]  
> If you encounter `ModuleNotFoundError`, ensure you have installed the requirements:  
> `pip install ".[examples]"`
