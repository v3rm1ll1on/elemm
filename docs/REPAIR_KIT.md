# Elemm Resilience: The Agent-Repair-Kit

Autonomous agents are prone to errors (hallucinations, typos, formatting issues). Traditional APIs return raw HTTP errors, which often lead to "Agent Loops" where the AI repeats the same mistake.

**Elemm's Agent-Repair-Kit breaks these loops by providing proactive, semantic self-healing.**

---

## 1. Automated Remedy Injection

Every landmark can define a `remedy`. This is a hand-crafted instruction that is **only** revealed when the agent makes a mistake.

### Example:
```python
@ai.action(
    id="update_profile",
    remedy="Always use YYYY-MM-DD for dates. Do not include time."
)
@app.post("/profile")
async def update(birth_date: str):
    # If the AI sends '12th June', FastAPI throws a 422.
    # Elemm intercepts this and returns the remedy.
```

### The AI-Native Error Response:
When a validation fails, Elemm returns a specialized JSON:
```json
{
  "status": "error",
  "error_type": "validation_failed",
  "managed_by": "elemm",
  "message": "The AI Agent sent an invalid request...",
  "remedy": "Always use YYYY-MM-DD for dates. Do not include time.",
  "instruction": "Follow the 'remedy' above to fix your parameters and try again.",
  "details": [...]
}
```

---

## 2. Advanced Noise Detection

Often, AI agents hallucinate extra parameters that are not in the API (e.g., trying to send a `confirmation: true` flag to a POST request).

The Repair-Kit includes a **Noise Detection Heuristic**:
- It compares the received JSON body keys against the allowed manifest keys.
- If it finds spurious fields, it adds a `noise_warning` to the error response.
- *Response:* `Action does not support these parameters: ['confirmation']. Stick to the manifest.`

---

## 3. How to write effective Remedies

A good remedy should be **Actionable**, **Specific**, and **Constraint-focused**.

| Bad Remedy | Good Remedy |
| :--- | :--- |
| "Invalid input" | "The ID must start with 'USR-' followed by 4 digits." |
| "Check your date" | "Ensure date is ISO-8601 formatted (e.g., 2024-01-01)." |
| "Too high" | "The amount must be between 1 and 100." |

---

## 4. Zero-Shot Error Recovery Flow

1.  **Agent attempts call** with a typo.
2.  **API returns 422** (Unprocessable Entity).
3.  **Repair-Kit intercepts**, finds the `remedy` for that specific landmark.
4.  **Agent receives the Remedy** + Noise warning.
5.  **Agent self-corrects** based on the specific instruction.

**Result:** The failure becomes a learning moment for the agent, leading to a successful second attempt without human intervention.
