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

## Contributor License Agreement (CLA)

Since Elemm is licensed under the Business Source License 1.1 (BSL 1.1) and transitions to the Mozilla Public License 2.0 (MPL 2.0), the Licensor (Marc Stöcker) must retain the right to license all contributions commercially (above the BSL thresholds). 

Therefore, by submitting a Pull Request to this project, you agree that your contributions are subject to the **Elemm Individual Contributor License Agreement (CLA)**.

### How to Sign the CLA
We use the automated **CLA Assistant** tool. When you open a Pull Request, our CLA Bot will automatically check if you have signed the agreement. If not, it will provide a link to sign it digitally with your GitHub account in one click.

### Summary of the CLA terms:
* **Retention of Ownership:** You retain the copyright and ownership of your code.
* **Grant of Rights:** You grant Marc Stöcker a perpetual, worldwide, non-exclusive, no-charge, royalty-free, irrevocable license to use, modify, sub-license, and distribute your contributions under any license, including commercial and proprietary licenses.
* **Originality:** You represent that your contribution is your original creation and you are legally entitled to grant these rights.
* **No Warranty:** Your contributions are provided "AS-IS", without warranties of any kind.

You can read the full text of the CLA in our [CLA.md](CLA.md) file in the root directory.

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
