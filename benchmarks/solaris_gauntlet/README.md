# Solaris Gauntlet - The Elemm Protocol Benchmark

The Solaris Gauntlet is a highly realistic benchmark environment designed to measure the efficiency of the **Elemm Protocol** in direct comparison to **Classic MCP** (standard Model Context Protocol).

## Benchmark Objective
The goal is to solve a complex, multi-stage forensic mission in an environment with massive "context noise" (over 100 tools). It measures how efficiently an LLM navigates the API, resolves dependencies, and passes variables between steps.

## How It Works

### Elemm Mode (`--mode elemm`)
Utilizes the native features of the protocol:
- **Manifest-Driven Discovery**: The model only sees the high-level manifest, not all 111 tool definitions at once.
- **Native Piping & Unboxing**: The model uses `$step0.field` syntax to pass data, instead of manually extracting it in the prompt.
- **SmartRepair**: Automatic correction suggestions for errors (agent guiding).

### Classic MCP Mode (`--mode classic`)
Simulates the standard approach:
- **Full Context Injection**: All 111 tool schemas are pumped into the context.
- **Manual Chaining**: The model must extract data from outputs and manually insert them into the next tool call.
- **Prompt Engineering Dependency**: Requires a massive "Technical Manual" in the system prompt to function at all.

---

## Benchmark Methodology: Solaris Gauntlet

The **Solaris Gauntlet** is a forensic security audit scenario designed to test an agent's ability to navigate complex, multi-domain toolsets under high pressure.

### The Scenario
A security breach (Incident SEC-9982) has been detected in the Solaris Enterprise Hub. The agent is cast as a **Forensic Auditor** with the task of resolving the incident.

### Objectives
To succeed, the agent must complete a 4-stage forensic chain:
1.  **Infrastructure Discovery**: Resolve the malicious IP (`10.0.4.142`) to a server hostname and audit its logs for evidence.
2.  **Entity Resolution**: Link log evidence (Evidence Tokens) to a Corporate Username and a Financial Account.
3.  **Cross-Domain Audit**: Resolve the Corporate Username to a real-world Employee ID via HR and audit recent transactions in Banking/Finance.
4.  **Remediation**: Execute a multi-step cleanup (Quarantine the account, restart the compromised node, and secure the risk capital).

### Complexity & Noise
- **Tool Volume**: The server provides **111 tools**. Only ~5% are relevant; the rest are "Noise Tools" (e.g., Marketing, Logistics) designed to distract the agent.
- **Logic Chains**: Tools are dependent on each other. You cannot quarantine an account without a verified `evidence_token`.
- **Constraint Enforcement**: The Elemm mode enforces protocol adherence (e.g., calling `get_manifest` first).

### Expectations & Metrics
- **Success Rate**: Did the agent reach the `MISSION_SUCCESS` state within 30 steps?
- **Step Efficiency**: How many turns did the agent need to resolve the logic chain?
- **Token Economy**: The core metric. How much context (USD cost) was consumed to reach the goal?
- **Resilience**: How well does the agent recover from "SmartRepair" nudges when it hits a protocol violation?

---

## Installation & Setup

1. **Dependencies**: Ensure the `venv` is active and `fastapi`, `uvicorn`, and `mcp` are installed.
2. **LLM**: By default, the benchmark uses `gemma4:e2b` (or your locally configured model) via Ollama on port 11434.

---

### Usage Examples

#### 1. Local Testing (Ollama)
The easiest way to start. No API keys required.
```bash
# Ensure Ollama is running locally
python3 benchmarks/solaris_gauntlet/benchmark_v2.py --mode compare --model gemma4:e2b -n 1
```

#### 2. Using OpenRouter (Claude, GPT-4, etc.)
Best for comparing different state-of-the-art models.
```bash
export OPENAI_BASE_URL="https://openrouter.ai/api/v1"
export PROVIDER_API_KEY="your_openrouter_key"

# Run Claude 3.5 Sonnet
python3 benchmarks/solaris_gauntlet/benchmark_v2.py --provider openai --model anthropic/claude-3.5-sonnet --mode compare -q
```

#### 3. Direct Google Gemini API (Google AI Studio)
Use your Gemini keys directly without a proxy.
```bash
export OPENAI_BASE_URL="https://generativelanguage.googleapis.com/v1beta/openai"
export PROVIDER_API_KEY="your_google_gemini_api_key"

# Run Gemini 1.5 Pro
python3 benchmarks/solaris_gauntlet/benchmark_v2.py --provider openai --model gemini-1.5-pro --mode compare -q
```

---

## CLI Parameters

| Flag | Description | Default |
| :--- | :--- | :--- |
| `--mode` | Mode: `elemm`, `classic`, or `compare` | `elemm` |
| `--provider` | API Provider: `ollama` or `openai` (use `openai` for Google/Claude/OpenRouter) | `ollama` |
| `--model` | LLM model name (e.g., `llama3`, `gemini-1.5-pro`) | `gemma4:e2b` |
| `-n` | Number of runs for statistical relevance | `1` |
| `--ctx` | Context window size (e.g., `32k`, `128k`) | `32k` |
| `-q`, `--quiet` | Suppresses step-by-step output | `False` |
| `-o`, `--output` | Writes the complete log to a file | `None` |

---

### SmartRepair & Protocol Guidance
This benchmark includes an automated **SmartRepair** system. If a model commits a protocol violation (e.g., trying to call a tool before getting the manifest), the benchmark extracts the `remedy` from the server response and injects it as a clear **Protocol Guidance** message. This helps even smaller models to successfully navigate the autonomous workflow.

---

## Example Commands

### 1. The "Smoking Gun" Comparison (Recommended)
Runs both modes alternately and displays a professional comparison table at the end, including cost savings and token reduction.
```bash
python3 benchmarks/solaris_gauntlet/benchmark_v2.py --mode compare -n 5 -q
```

### 2. Stress Test (Massive Context)
Tests Elemm with a small context window (8k) and many noise tools to verify the robustness of manifest discovery.
```bash
python3 benchmarks/solaris_gauntlet/benchmark_v2.py --mode elemm --ctx 8k -n 10
```

### 3. Debugging Run
Displays every single thought and tool call of the model in detail.
```bash
python3 benchmarks/solaris_gauntlet/benchmark_v2.py --mode elemm -n 1
```

---

## Evaluation Metrics

- **Success Rate**: Percentage of successfully completed missions.
- **Avg Steps**: How many turns does the model need? (Elemm usually takes 2-3, Classic often 7-10).
- **Avg Tokens In**: The most important indicator for **cost**. (Elemm typically saves >85%).
- **Est. Total Cost**: Projected costs for major LLM providers (Gemini, GPT-4, Claude).

---

## Benchmark Structure
- `benchmark_v2.py`: The core engine (async, multi-run, reporting).
- `api_elemm_v2.py`: The Elemm server with landmarks.
- `mcp_classic.py`: The standard MCP server wrapper.
- `landmarks_v2.yaml`: The metadata definition for Elemm.
- `shared_db.py`: Shared in-memory database for fair comparisons.
`: Shared in-memory database for fair comparisons.
