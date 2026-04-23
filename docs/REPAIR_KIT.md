# Elemm Resilience: The Agent Repair Kit

AI agents are prone to errors such as typos, incorrect date formats, or hallucinating parameters. In these cases, traditional APIs often only deliver technical error messages (e.g., "422 Unprocessable Entity"), which frequently leads to infinite loops where the agent repeats the same mistake.

The Elemm Agent Repair Kit breaks these loops through proactive, semantic self-healing.

Instead of keeping these instructions permanently in the tool description (which costs tokens), they are delivered only in case of an error.

### Static vs. Dynamic Remedies

You can provide remedies in two ways:
1. **Static (via Decorator)**: Best for general formatting or constant rules.
2. **Dynamic (via Code Logic)**: Best for complex validation that depends on specific input values.

#### Native Python: Dynamic Remedies via `ActionError`

If you are using Elemm without FastAPI, you can use the `ActionError` exception to provide situational hints:

```python
from elemm.core.exceptions import ActionError

@manager.action(id="process_payment")
def pay(amount: int, currency: str):
    if amount > 1000:
        # Dynamic remedy based on the specific error condition
        raise ActionError(
            message="Limit exceeded",
            remedy="Payments over 1000 require 'manager_approval: true'."
        )
    if currency != "EUR":
        raise ActionError(
            message="Invalid currency",
            remedy="We only support 'EUR' for this operation."
        )
    return {"status": "success"}
```

When an `ActionError` is raised, Elemm automatically extracts the `remedy` and places it at the very top of the agent's feedback.

## 2. Automated Noise Detection

AI agents often invent parameters that do not exist in the API (e.g., a `confirm: true` field during a deletion process).

The repair kit recognizes these deviations:
- It compares the received JSON keys with the parameters defined in the manifest.
- Surplus fields are identified and returned to the agent as a `noise_warning`.
- The response then reads: "The action does not support these parameters: ['confirm']. Stick strictly to the manifest."

## 3. Zero-Shot Error Recovery Flow

The correction process runs fully automatically:

1. **Attempted Call**: The agent sends an erroneous request.
2. **Interception**:
    - **FastAPI**: Elemm recognizes HTTP error codes (400, 422, 500).
    - **Native Python**: Elemm catches uncaught exceptions or explicit `ActionError` calls.
3. **Enrichment**: The error response is enriched with the specific `remedy` (static or dynamic) and, if applicable, a `noise_warning`.
4. **Instruction**: The agent is explicitly told: "Use the above remedy to correct your parameters and try again."
5. **Self-Correction**: The agent uses the hint and executes a successful call on the second attempt.

## 4. Writing Effective Remedies

Good correction hints are precise and action-oriented.

| Bad Remedy | Good Remedy |
| :--- | :--- |
| "Invalid input" | "The ID must start with 'USR-' followed by 4 digits." |
| "Check the date" | "Ensure the date is ISO-8601 formatted (e.g., 2024-01-01)." |
| "Value too high" | "The amount must be between 1 and 100." |

With the Agent Repair Kit, every error becomes a learning moment for the agent, which significantly increases the success rate for complex tasks.
