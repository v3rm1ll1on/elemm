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

In standardized tests using 120B parameter models, the Landmark Manifest Protocol significantly outperforms traditional MCP in every economic and operational metric:

| Metric | Classic MCP | Elemm Protocol | Improvement |
| :--- | :--- | :--- | :--- |
| **Success Rate** | 100.0% | 100.0% | Parity |
| **Avg. Steps** | 12.50 | **2.00** | **-84%** |
| **Input Tokens** | 88,032 | **7,061** | **-92%** |
| **Output Tokens** | 2,298 | **741** | **-67%** |
| **Total Cost (Est.)** | $2.04 | **$0.23** | **-88%** |

---

## Key Efficiency Drivers

### 1. Context Optimization
By isolating tool signatures within Landmarks and only loading them upon discovery, Elemm reduces the initial prompt size by over 90%. This prevents "Context Fatigue" and model hallucinations.

### 2. Turn Consolidation
The `execute_sequence` command allows the agent to plan and execute complex logic chains in a single turn. What typically requires 12+ roundtrips in standard MCP is resolved in just 2 turns with Elemm.

### 3. Server-Side Piping
Native variable piping (`$step0.id`) eliminates the need for the LLM to manually extract, store, and re-inject data into subsequent prompts, further reducing token consumption and processing latency.

---

## Economic Impact

Implementing the Landmark Manifest Protocol directly translates to a massive reduction in operational API costs. In complex administrative scenarios, Elemm can achieve up to **88% cost reduction** compared to standard tool-calling implementations.
