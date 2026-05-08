# 🌌 Elemm (Element Mapping) v2

**Autonomous. Efficient. Reliable.**

Elemm is a next-generation protocol for AI agents, designed to bridge the gap between static tool definitions and autonomous complex reasoning. It optimizes token consumption, reduces execution latency, and provides a robust self-healing framework for agentic workflows.

---

## 🚀 Key Features
- **Semantic Landmarks**: Group tools into logical namespaces for better discovery.
- **High-Performance Sequencing**: Execute multi-step chains in a single LLM turn.
- **SmartRepair Engine**: Provide agents with actionable remedies for protocol errors.
- **Variable Piping**: Seamless data flow between tools with zero-latency resolution.
- **Python-First Workflow**: Define tools via decorators and Pydantic models with automatic schema generation.
- **Benchmark Proven**: Up to 90% token savings and 70% fewer turns compared to standard MCP.

---

## 📚 Documentation
- **[Getting Started](docs/GETTING_STARTED.md)**: Install and run your first landmark.
- **[Developer Guide](docs/DEVELOPER_GUIDE.md)**: Build your own tools with decorators and Pydantic.
- **[Architecture Overview](docs/ARCHITECTURE.md)**: Deep dive into the Elemm philosophy.
- **[Protocol Specification](docs/PROTOCOL_SPEC.md)**: Technical details for implementers.
- **[Benchmarking Results](docs/BENCHMARKING.md)**: See how Elemm crushes standard MCP.

---

## 🏎️ Quick Start (The Easy Way)
1. **Install**: `pip install elemm`
2. **Connect**: Add `mcp.py` to your Claude Desktop config:
```json
"elemm": {
  "command": "python3",
  "args": ["/path/to/elemm/examples/mcp.py", "http://localhost:8000"]
}
```
*Note: Make sure your Elemm-powered site is running on port 8000.*

## ⚖️ License
Copyright (C) 2026 Marc Stöcker.
GPLv3 License. See [LICENSE](LICENSE) for details.
