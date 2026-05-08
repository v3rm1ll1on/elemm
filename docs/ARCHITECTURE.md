# 🏛️ Elemm v2 Architecture Overview

## The Philosophy: Landmarks vs. Flat Toolsets
Traditional MCP implementations often overwhelm agents with a flat list of dozens of tools. This leads to "Context Bloating," high latency, and frequent model hallucinations.

**Elemm (Element Mapping)** introduces the concept of **Landmarks**:
- **Landmarks** are semantic namespaces (clusters) of related functionality.
- **Lazy Loading**: Agents only see high-level descriptions first. They must "inspect" a landmark to get detailed technical signatures.
- **Discovery-Driven**: The protocol forces the agent to explore and understand the environment before executing high-stakes operations.

---

## 🛰️ The Discovery Cycle
The Elemm protocol follows a strict three-stage handshake:

1.  **`get_manifest()`**: The agent requests the system summary. It receives a list of available Landmarks and their high-level purpose, but NO tool signatures yet.
2.  **`inspect_landmark(id)`**: The agent selects relevant namespaces based on the task and requests their technical signatures (TypeScript-style).
3.  **Execution**: Once technical requirements are known, the agent proceeds to call tools.

---

## ⚡ The Execution Engine
Elemm supports two modes of interaction:

### 1. Atomic Actions (`call_action`)
A single request-response cycle for simple, independent tasks.

### 2. High-Performance Pipelines (`execute_sequence`)
The core strength of Elemm. It allows chaining multiple actions into a single "Turn."
- **Variable Piping**: Results from Step 0 can be passed to Step 1 using `$step0.fieldname`.
- **Zero-Latency Chaining**: The entire sequence is executed server-side, eliminating back-and-forth roundtrips to the LLM.
- **Memory Bank**: Every result in a sequence is automatically indexed and available for subsequent steps.

---

## 🛡️ SmartRepair & Forensic Auditing
Elemm is designed for **Autonomous Reliability**. If an agent makes a mistake (e.g., calling a tool directly or using wrong parameters), the system doesn't just error out:

- **Remediation Messages**: Every error includes a `remedy` field explaining *exactly* how to fix the call.
- **Protocol Hardening**: Strict validation ensures agents cannot bypass the discovery phase.
- **Forensic Logs**: Every action, piped variable, and repair attempt is logged for auditability.

---

## 🛠️ Component Breakdown

| Component | Responsibility |
| :--- | :--- |
| **AIProtocolManager** | Orchestrates registration, execution, and memory state. |
| **ManifestPresenter** | Generates adaptive markdown summaries (Summary vs. Full). |
| **SmartRepairEngine** | Analyzes failures and provides actionable recovery guidance. |
| **Gateways (MCP/FastAPI)** | Bridges the core logic to standard communication protocols. |
