# Elemm Architecture Overview

The Landmark Manifest Protocol is designed to solve the inherent scalability issues of standard tool-calling protocols.

---

## The Problem: The Swiss Army Knife Paradox

Standard AI toolsets (like basic MCP) often provide an agent with all available tools at once. 
As the toolset grows (e.g., 50+ tools), the following issues emerge:
- **Context Bloating**: The system prompt becomes massive, consuming tokens and increasing costs.
- **Latency**: Large prompts increase time-to-first-token.
- **Hallucinations**: The model loses focus and starts confusing similar tools or ignoring constraints.

---

## The Solution: Semantic Landmarks

Elemm solves this through a tiered discovery system called **Landmarks**:
- **Landmarks** function as an interactive table of contents.
- The agent initially only sees the high-level namespaces (e.g., `Security`, `IT`, `HR`).
- Detailed tool signatures are only loaded when the agent proactively "steps into" a specific landmark.
- This keeps the agent's context clean and focuses its reasoning power on the relevant subset of tools.

---

## The Discovery Cycle

The protocol follows a three-stage handshake:

1.  **Manifest Discovery**: The agent calls `get_manifest()` to receive a summary of available landmarks and their purpose. No tool signatures are provided at this stage.
2.  **Landmark Inspection**: Based on the task, the agent selects relevant landmarks and calls `inspect_landmarks(ids)` to retrieve full technical schemas.
3.  **Execution**: The agent proceeds with tool execution once it has the required signatures.

---

## High-Performance Execution Engine

Elemm supports advanced execution patterns to minimize turn-around time:

### Atomic Actions
Standard request-response cycles for independent tasks via `call_action`.

### High-Performance Sequences
The `execute_sequence` command allows chaining multiple actions into a single LLM turn:
- **Native Piping**: Use results from previous steps (e.g., `$step0.id`) directly in subsequent commands.
- **Server-Side Execution**: The entire chain is resolved on the server, eliminating the need for multiple roundtrips to the LLM.
- **Conditional Logic**: Supports conditional execution based on the success or failure of previous steps.

---

## Autonomous Reliability (SmartRepair)

Elemm is built for autonomous systems where human intervention is minimized:

- **Remedy Injection**: Technical errors are supplemented with human-readable "remedies". If an agent fails, it receives clear instructions on how to correct its path.
- **Validation Hardening**: Strict validation ensures that agents follow the discovery protocol and use valid, real-world data instead of placeholders.
- **Type Mapping**: Automatic translation of Python types (Pydantic, Literals) into high-fidelity schemas for the LLM.
- **Forensic Auditing**: Every action and piped variable resolution is logged for complete auditability.
