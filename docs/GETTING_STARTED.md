# Getting Started with Elemm

Welcome to Elemm! This guide will help you set up your first autonomous tool environment using the Landmark Manifest Protocol.

---

## 1. Installation

Install Elemm directly from PyPI:

```bash
pip install elemm
```

---

## 2. Define your first Landmark Server

Elemm organizes tools into **Landmarks** (logical namespaces). Use the `ElemmGateway` to define your actions:

```python
from elemm import ElemmGateway

gateway = ElemmGateway(name="MyHomeAutomation")

@gateway.action(landmark="Lighting")
async def set_brightness(room: str, level: int):
    """Sets the brightness level (0-100) for a specific room."""
    return {"room": room, "brightness": level, "status": "adjusted"}

if __name__ == "__main__":
    # Start as FastAPI server
    gateway.run(port=8000)
    
    # OR start as MCP server (STDIO)
    # gateway.run_mcp()
```

---

## 3. How Agents Interact with Elemm

When an agent (like Claude or Gemini) connects to your Elemm server, it follows a structured discovery path:

1.  **Get Manifest**: The agent calls `get_manifest()` and sees a list of available landmarks (e.g., "Lighting").
2.  **Inspect Landmarks**: The agent calls `inspect_landmarks(landmark_id="Lighting")` to receive the full JSON schemas for all tools in that namespace.
3.  **Execute Sequence**: For complex tasks, the agent can call `execute_sequence()` to run multiple steps in one turn, using results from previous steps (e.g., `$step0.id`).

---

## 4. Connecting to Claude Desktop

To use your Elemm server with Claude Desktop, add the following to your `claude_desktop_config.json`:

```json
"elemm-home": {
  "command": "python3",
  "args": ["-m", "elemm.integrations.mcp_bridge", "http://localhost:8000"]
}
```

---

## 5. Next Steps

*   **[Developer Guide](DEVELOPER_GUIDE.md)**: Learn about Pydantic integration and SmartRepair.
*   **[Architecture Overview](ARCHITECTURE.md)**: Understand the "Landmark" philosophy.
*   **[Benchmarking Results](BENCHMARKING.md)**: See performance comparisons.
