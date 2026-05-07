<div align="center">
  <h1>Elemm: LLM Landmark Protocol</h1>
  <p><strong>The Execution Layer for Domain-Agnostic AI Agents</strong></p>

  [![PyPI version](https://img.shields.io/pypi/v/elemm.svg)](https://pypi.org/project/elemm/)
  [![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
  [![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
</div>

---

**Elemm** is a communication protocol designed to transform how Large Language Models (LLMs) interact with complex API ecosystems. It moves beyond simple tool-calling by introducing a structured **Autonomous Execution Layer**. 

By shifting the burden of state management and data piping from the AI model to the protocol itself, Elemm achieves up to **96% token efficiency** and enables even **ultra-small local models (0.8b)** to solve multi-step forensic and administrative tasks with high reliability.

---

## Why Elemm?

In a classic setup, agents struggle with context noise and hallucination fatigue as the number of tools grows. Elemm eliminates these bottlenecks:

- **Manifest-Driven Discovery**: Agents only see a high-level Landmark Topology initially. Technical details are requested just-in-time, keeping the context window clean.
- **Sequence Engine & Smart Piping**: Instead of calling tools one by one, the agent submits a Sequence. Elemm automatically pipes output from one step (e.g., `$step0.hostname`) into the next, preventing ID hallucinations.
- **Forensic Context Hygiene**: Successful steps are automatically compacted in the logs, preserving context space for active reasoning and complex error handling.
- **SmartRepair**: If a sequence fails, the protocol provides structured forensic feedback, including available data keys and remedy instructions, guiding the agent to self-correct instantly.

---

## Performance Benchmark Results

| Metric | Classic Mode | Elemm Mode | Efficiency Gain |
| :--- | :--- | :--- | :--- |
| **Initial Context Size** | ~5,600 Tokens | **~450 Tokens** | **-92% Noise** |
| **Turns to Solve Mission** | 12+ Turns | **2 Turns** | **-80% Latency** |
| **Total Compute Cost** | ~104,000 Tokens | **~3,600 Tokens** | **96.5% Savings** |
| **Small Model (0.8b) Success** | ~0% | **80% (Verified)** | **Reliable Execution** |

---

## Core Components

### 1. The Protocol Manifest
The `.well-known/elemm-manifest.md` serves as the agent's map. It contains the Agent Directive (SOP) and the Landmark Topology, defining available namespaces without overwhelming the model with technical schemas.

### 2. Landmark Registry (YAML)
Elemm uses a central `landmarks.yaml` to define the technical metadata for all tools. This file is the "Source of Truth" for:
- **Technical Signatures:** Tool parameters and return types.
- **Landmark Mapping:** Grouping tools into logical domains.
- **Smart Hints:** Providing `remedy` instructions for failed execution turns.

### 3. Autonomous Data Piping (LLM Native)
Elemm enables the LLM to autonomously chain actions without manual variable management. The model uses the `$alias.field` syntax within an `execute_sequence` call to pass data between tools dynamically:
```json
{
  "action": "execute_sequence",
  "actions": [
    { "action": "noc:get_host", "alias": "srv", "parameters": {"ip": "10.0.4.1"} },
    { "action": "it:query_logs", "parameters": {"host": "$srv.hostname"} }
  ]
}
```

---

## Quick Start

### 1. Installation
```bash
pip install elemm
```

### 2. Integration with FastAPI
Ideal for exposing existing web APIs to AI agents.

```python
from fastapi import FastAPI
from elemm import AIProtocolManager
from elemm.gateways.fastapi import FastAPIGateway

app = FastAPI()

# 1. Initialize the Manager and load metadata
manager = AIProtocolManager()
manager.load_metadata("landmarks.yaml")

# 2. Bind your FastAPI endpoints to Action IDs
@app.get("/noc/resolve")
@manager.bind("noc:resolve_ip_to_host") # Decorator automatically binds the endpoint to the action ID.
async def resolve_ip(ip: str):
    return {"hostname": "SRV-01"}

@app.get("/it/logs")
@manager.bind("it_ops:query_node_logs") # Decorator automatically binds the endpoint to the action ID.
async def get_logs(hostname: str):
    return [{"ts": "2024-01-01", "msg": "System boot"}]

# 3. Launch the Gateway
gateway = FastAPIGateway(manager)
gateway.bind_to_app(app)
```

### 3. Native MCP Server (Stdio/CLI)
Ideal for local tools and command-line utilities without a web server.

```python
from elemm import AIProtocolManager
from elemm.gateways.mcp_server import MCPGateway

# 1. Initialize and load metadata
manager = AIProtocolManager()
manager.load_metadata("landmarks.yaml")

# 2. Bind standard Python functions
@manager.bind("noc:resolve_ip_to_host") # Decorator automatically binds the endpoint to the action ID.
async def resolve_ip(ip: str):
    return {"hostname": "SRV-01"}

@manager.bind("it_ops:query_node_logs") # Decorator automatically binds the endpoint to the action ID.
async def get_logs(hostname: str):
    return [{"ts": "2024-01-01", "msg": "System boot"}]

# 3. Launch as Stdio-based MCP server
gateway = MCPGateway(manager)
gateway.run_stdio()
```

### 4. Landmark Configuration Example
Define your structure in `landmarks.yaml`:
```yaml
instructions: "MANDATORY: Resolve IPs via NOC before searching logs."
landmarks:
  - id: "noc"
    notes: "Network Operations Center for IP resolution."
  - id: "it_ops"
    notes: "IT Infrastructure logs and forensic data."

actions:
  - id: "noc:resolve_ip_to_host"
    landmark: "noc"
    description: "Resolves an internal IP to a server hostname."
    parameters:
      ip: { type: "string", description: "The target IP address." }

  - id: "it_ops:query_node_logs"
    landmark: "it_ops"
    description: "Queries infrastructure logs for a specific host."
    parameters:
      hostname: { type: "string", description: "Target server hostname." }
```

---

## License

Elemm is free software: you can redistribute it and/or modify it under the terms of the **GNU General Public License v3.0**. 

**Elemm: Efficient, structured, and autonomous tool interaction.**
