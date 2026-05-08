# 📊 Elemm Performance Benchmarking

Elemm is built for efficiency. We use the **Solaris Gauntlet**—a complex multi-step forensic audit task—to measure how well our protocol performs compared to standard "flat" MCP implementations.

---

## 🏎️ Running the Benchmarks
The benchmark suite is located in `benchmarks/solaris_gauntlet/`.

### Standard Run (Elemm v2)
```bash
python3 benchmarks/solaris_gauntlet/benchmark_v2.py --mode elemm -n 10
```

### Classic Comparison (Standard MCP)
```bash
python3 benchmarks/solaris_gauntlet/benchmark_v2.py --mode classic -n 10
```

---

## 📈 Real-World Results (Gemma 2b)
In our tests with the Gemma 2b model, Elemm v2 outperformed the classic approach in every metric:

| Metric | Classic MCP | Elemm v2 | Improvement |
| :--- | :--- | :--- | :--- |
| **Success Rate** | 80.0% | **100.0%** | **+25%** |
| **Avg. Steps** | 16.20 | **4.90** | **-70%** |
| **Input Tokens** | 148,726 | **15,900** | **-89%** |
| **Peak Context** | 10,529 | **3,965** | **-62%** |
| **Duration** | 27.12s | **14.10s** | **-48%** |

---

## 🧠 Key Findings
1.  **Token Efficiency**: By hiding tool signatures until they are needed, we reduce the initial prompt size by up to 90%.
2.  **Turn Reduction**: `execute_sequence` allows the agent to plan and execute a 9-step forensic chain in a single turn.
3.  **Stability**: The strict discovery cycle prevents the model from "guessing" tool names, leading to a perfect success rate even on smaller models.

---

## 💰 Cost Impact
Using Elemm directly translates to lower API costs. In our tests, an Elemm mission on GPT-4o cost **70% less** than the same mission in Classic mode.
