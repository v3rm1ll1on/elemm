# Elemm Security: Shielding & Read-Only 🛡️

Elemm is designed to be "Secure by Default". It acts as a safety layer between the Autonomous Agent and your sensitive backend logic.

---

## 1. Managed Authentication (Auto-Shield)

A common mistake in AI-tooling is feeding raw authentication headers to the LLM. 
- **The Risk**: The LLM might try to guess credentials, leak them in conversations, or hallucinate security tokens.
- **The Elemm Solution**: Elemm automatically detects FastAPI security dependencies (`HTTPBearer`, `APIKeyHeader`, `OAuth2PasswordBearer`).

### How it works:
When Elemm finds a security scheme, it does two things:
1.  **Shielding**: The parameter is removed from the agent's visible input list.
2.  **Marking**: It is marked as `managed_by: protocol` in the manifest.

```python
from fastapi.security import HTTPBearer
auth_scheme = HTTPBearer()

@ai.action(id="delete_user")
@app.delete("/users/{id}")
async def delete(id: str, token: str = Depends(auth_scheme)):
    # The agent NEVER sees the 'token' parameter. 
    # It only sees 'id'.
    return {"status": "deleted"}
```

---

## 2. Dynamic Read-Only Mode

You can enforce a globally safe environment for your AI with a single flag.

### Enabling Read-Only
- **Via Environment**: Set `LANDMARK_READ_ONLY=True`.
- **Via URL**: Append `?read_only=true` to the manifest URL.

### What happens?
When Read-Only is active, Elemm dynamically filters the manifest:
- **Stripped**: All landmarks of `type="write"`.
- **Stripped**: All landmarks using `POST`, `PUT`, `PATCH`, or `DELETE` methods.
- **Result**: The AI physically cannot see or call state-changing tools.

---

## 3. Context Injection & Data Hygiene

Elemm automatically hides "technical noise" that often clutters LLM reasoning:
- **Request/Response Objects**: Automatically hidden.
- **Background Tasks**: Automatically hidden.
- **Internal IDs**: If a dependency is detected as an internal service, it is excluded from the manifest.

This ensures the agent focuses **only** on business logic parameters, reducing the risk of unintended exploitation of internal API structures.

---

## 4. Best Practices for Production

1.  **Use Scopes**: Always use FastAPI `Depends` for authorization. Elemm will pick them up and shield them.
2.  **Sanitize Descriptions**: Never put sensitive internal server names or IP addresses in landmark descriptions.
3.  **Audit the Well-Known**: Regularly check `/.well-known/llm-landmarks.json` to see exactly what the AI sees.
