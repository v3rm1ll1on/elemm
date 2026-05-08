# 🏛 Elemm v2 Architecture Overview

##  The Problem: "The Swiss Army Knife Paradox"
Standard AI toolsets (like basic MCP) often give an agent 50+ tools at once. 
**The result:** The agent gets confused (Context Bloating), gets slow, and starts hallucinating. It's like giving someone a 1000-page manual and asking them to find one specific screw.

**Elemm (Element Mapping)** solves this with **Landmarks**:
- **Landmarks** are like an **"Interactive Table of Contents"**.
- The agent only sees the "Chapters" (Landmarks) first.
- It must **proactively explore** the chapter it needs before getting the technical details.
- This keeps the agent's memory clean and its focus sharp.

---

## 🛰 The Discovery Cycle
The Elemm protocol follows a strict three-stage handshake:

1.  **`get_manifest()`**: The agent requests the system summary. It receives a list of available Landmarks and their high-level purpose, but NO tool signatures yet.
2.  **`inspect_landmarks(landmark_ids)`**: The agent selects relevant namespaces based on the task and requests their technical signatures (TypeScript-style).
3.  **Execution**: Once technical requirements (including valid `options` as TypeScript Unions) are known, the agent proceeds to call tools.

---

## ⚡ The Execution Engine
Elemm supports two modes of interaction:

### 1. Atomic Actions (`call_action`)
A single request-response cycle for simple, independent tasks.

### 2. High-Performance Pipelines (`execute_sequence`)
The core strength of Elemm. It allows chaining multiple actions into a single "Turn."
- **Zero-Latency Chaining**: The entire sequence is executed server-side, eliminating back-and-forth roundtrips to the LLM.
- **Conditional Execution**: Actions within a sequence can be skipped based on server-side evaluation of previous results.
- **Interpolation Engine**: The execution engine can inject piped values directly into string parameters, enabling complex dynamic commands.
- **Memory Bank**: Every result in a sequence is automatically indexed (e.g., `$step0`) and available for subsequent steps.

---

## 🛡 SmartRepair & Forensic Auditing
Elemm is designed for **Autonomous Reliability**. If an agent makes a mistake (e.g., calling a tool directly or using wrong parameters), the system doesn't just error out:

- **Remedy Shadowing**: To prevent AI confusion, low-level technical stack traces are "shadowed" by high-level instructions (remedies) defined in the protocol registry. The agent sees a clear path to recovery instead of raw code errors.
- **Context Isolation & Persistence**: Elemm utilizes `ContextVar` to isolate data between different landmarks and maintain session persistence (e.g., auth tokens) across tools.
- **Protocol Hardening**: Strict validation ensures agents cannot bypass the discovery phase. Direct calls to underlying tools without the `call_action` wrapper are blocked via a mandatory "Safety Lock".
- **Intelligent Type Mapping**: The discovery engine automatically maps complex Python types (Pydantic, Literals, Enums) to the protocol, ensuring high-fidelity schemas for the LLM.
- **Placeholder Detection**: The system identifies and rejects common AI "hallucination placeholders" like `UNKNOWN` or `[INSERT DATA]`, forcing the agent to fetch real data.
- **Forensic Logs**: Every action, piped variable, and repair attempt is logged for auditability.

---

##  Component Breakdown

| Component | Responsibility |
| :--- | :--- |
| **AIProtocolManager** | Orchestrates registration, execution, and memory state. |
| **ManifestPresenter** | Generates adaptive markdown summaries (Summary vs. Full). |
| **SmartRepairEngine** | Analyzes failures and provides actionable recovery guidance. |
| **Gateways (MCP/FastAPI)** | Bridges the core logic to standard communication protocols. |
