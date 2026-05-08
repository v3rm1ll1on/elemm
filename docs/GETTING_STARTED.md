# 🚀 Getting Started with Elemm v2

Welcome to Elemm! This guide will help you set up your first autonomous tool environment in minutes.

---

## 1. Installation
Clone the repository and set up a virtual environment:

```bash
git clone https://github.com/v3rm1ll1on/elemm.git
cd elemm
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

---

## 2. Define your Landmarks
Create a `landmarks.yaml` file to define your tools. This is your source of truth.

```yaml
landmarks:
  - id: "weather"
    description: "Real-time meteorological data."
    tools:
      - id: "get_forecast"
        description: "Get the 5-day forecast for a city."
        parameters:
          - name: "city"
            type: "string"
            required: true
        returns: "{ temp: number, condition: string }"
```

---

## 3. Launch the MCP Server
Elemm comes with a built-in MCP Gateway. You can run it directly via the CLI:

```bash
python3 -m elemm.gateways.mcp_server --config landmarks.yaml
```

Now, any MCP-compatible agent (like Claude Desktop or Gemini) can connect to this server.

---

## 4. Using Elemm with an Agent
Once the agent is connected, the standard workflow is:

1. **Agent calls `get_manifest()`**: "Okay, I see there is a 'weather' landmark."
2. **Agent calls `inspect_landmarks(landmark_ids=["weather"])`**: "I see `get_forecast` takes a `city` parameter and returns `temp`."
3. **Agent calls `call_action()`**: "Executing `weather:get_forecast(city='Berlin')`."

---

## 5. Next Steps
- Explore **`docs/ARCHITECTURE.md`** to understand the core concepts.
- Check **`docs/BENCHMARKING.md`** to see how to run performance tests.
- Dive into **`docs/PROTOCOL_SPEC.md`** for advanced configuration.
