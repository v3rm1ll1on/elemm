# 🏠 SmartHome v2 Example

This example demonstrates the Elemm v2 architecture in a smart home context. It showcases how to separate tool definitions from implementation and how to use high-performance sequences to control devices.

## 🚀 Running the Example

### As a Native MCP Server (Default)
This is the recommended way to use it with agents like Claude Desktop.
```bash
python3 examples/smart_home/smarthome_v2.py
```

### As a FastAPI Web Server
If you want to inspect the protocol via HTTP:
```bash
python3 examples/smart_home/smarthome_v2.py --fastapi
```

---

## 🛠️ Key Features

### 1. Separation of Concerns
- **`landmarks.yaml`**: Pure declaration of landmarks, tools, and technical signatures. No logic.
- **`smarthome_v2.py`**: Implementation of handlers and registration to the `LandmarkManager`.

### 2. Native Sequencing
Because we use the `LandmarkManager`, this example supports the `execute_sequence` tool out of the box. An agent can now perform complex tasks in a single turn:

**Example Task**: *"Find the heating in the living room and set it to 22 degrees."*

**Sequence Execution**:
1. `discovery:find_device(room_id="living-room", device_type="heating")` (alias: `heat`)
2. `smart_control:control_device(device_id="$heat.id", temperature=22)`

The entire logic above is resolved and executed server-side in one roundtrip.

### 3. SmartRepair
If you try to turn off the fridge, the `smart_control:control_device` handler returns a specific error message which is then presented to the agent as a protocol-compliant repair hint.
