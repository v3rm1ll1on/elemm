# Contributing to Elemm

First off, thank you for considering contributing to Elemm! It's people like you that make Elemm such a great tool for the AI community.

## Our Philosophy
Elemm is built to be **lightweight, fast, and framework-agnostic**. We value:
1. **Simplicity**: The core should remain small and understandable.
2. **Efficiency**: Token usage is our most important metric. If a feature adds significant token overhead without a clear benefit, we will likely reject it.
3. **Compatibility**: Native Python first. Framework integrations (like FastAPI) should be kept in their respective sub-packages.

## How Can I Contribute?

### Reporting Bugs
- Use the GitHub Issue Tracker.
- Describe the expected behavior and the actual behavior.
- Provide a minimal reproducible example (code snippet).
- Mention your Python version and your LLM client (e.g. AnythingLLM, Claude Desktop).

### Suggesting Enhancements
- Open an issue first to discuss the idea. We want to avoid "feature creep" to keep the core stable and fast.

### Pull Requests
1. Fork the repository and create your branch from `dev`.
2. Ensure `pytest` passes 100%.
3. Follow the existing code style (clean, PEP8-ish, documented).
4. Update documentation in the `docs/` folder if you change or add features.
5. Add a test case in the `tests/` directory if you add a new feature or fix a bug.

## Development Setup
```bash
# Clone the repository
git clone https://github.com/v3rm1ll1on/elemm.git
cd elemm

# Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install in editable mode with dev dependencies
pip install -e .[fastapi,examples]
pip install pytest pytest-asyncio

# Run tests
PYTHONPATH=src pytest tests/
```
