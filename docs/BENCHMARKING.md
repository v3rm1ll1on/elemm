# Elemm Performance Benchmarking

The Landmark Manifest Protocol is built for industrial-scale efficiency. We use the **Solaris Gauntlet**—a complex multi-step forensic audit task involving 111 tools—to measure performance compared to standard "flat" MCP implementations.

---

## Running the Benchmarks

The benchmark suite is located in `benchmarks/solaris_gauntlet/`.

### Head-to-Head Comparison
To compare Elemm directly against Classic MCP across multiple runs:
```bash
python3 benchmarks/solaris_gauntlet/benchmark_v2.py --mode compare -n 10 -q
```

### Individual Modes
```bash
# Test Elemm efficiency
python3 benchmarks/solaris_gauntlet/benchmark_v2.py --mode elemm -n 10

# Test Classic MCP overhead
python3 benchmarks/solaris_gauntlet/benchmark_v2.py --mode classic -n 10
```

---

## Comparative Performance Analysis

In standardized tests using 120B parameter models (gpt-oss-120b (free) on openrouter.ai), the Landmark Manifest Protocol significantly outperforms traditional MCP in every operational and economic metric:

| Metric | Classic MCP | Elemm Protocol | Improvement |
| :--- | :--- | :--- | :--- |
| **Success Rate** | 100.0% | 100.0% | Parity |
| **Avg. Steps** | 12.80 | **2.00** | **-84.4%** |
| **Input Tokens (Avg)** | 92,024 | **7,081** | **-92.3%** |
| **Output Tokens (Avg)** | 2,545 | **692** | **-72.8%** |
| **Total Tokens (10 runs)**| 945,697 | **77,744** | **-91.8%** |
| **Avg. Duration** | 65.35s | **23.72s** | **-63.7%** |
| **Total Cost (Est.)** | $2.15 | **$0.22** | **-89.5%** |

*Methodology: Results were averaged over 10 consecutive runs with an identical task description.*

---

## Key Efficiency Drivers

### 1. Context Optimization
By isolating tool signatures within Landmarks and only loading them upon discovery, Elemm reduces the initial prompt size by over 90%. This prevents "Context Fatigue" and model hallucinations.

### 2. Turn Consolidation
The `execute_sequence` command allows the agent to plan and execute complex logic chains in a single turn. What typically requires 12+ roundtrips in standard MCP is resolved in just 2 turns with Elemm.

### 3. Server-Side Piping
Native variable piping (`$step0.id`) eliminates the need for the LLM to manually extract, store, and re-inject data into subsequent prompts, further reducing token consumption and processing latency.

### 4. Infrastructure & Caching Advantage
Standard MCP is "noisy"—each turn modifies the prompt, often invalidating context caches. Elemm's high-stability prefix (System Prompt + Manifest) ensures a near 100% cache hit rate for the heaviest part of the payload (tool definitions). This leads to faster Time-To-First-Token (TTFT) and significantly lower costs on providers with prompt-caching (OpenAI) or context-caching (Gemini).

---

## Economic Impact

Implementing the Landmark Manifest Protocol directly translates to a massive reduction in operational API costs. In complex administrative scenarios, Elemm can achieve an average of **89.5% cost reduction** compared to standard tool-calling implementations.

---

## Edge Case: Ultra-Lightweight Models (SLMs)

Elemm significantly lowers the barrier for entry-level models. In tests using **0.8B parameter models** (e.g., Qwen 3.5) with a **64k context window**, the protocol demonstrates extreme resilience:

| Scenario | Classic MCP Success | Elemm Success | Improvement |
| :--- | :--- | :--- | :--- |
| **Forensic Audit (0.8B)** | 10.0% | **70.0%** | **+600%** |

*Methodology: Small models often struggle with high-cardinality toolsets. Elemm's landmark categorization prevents the model from being overwhelmed by 100+ tool signatures at once, making SLMs viable for complex automation.*
