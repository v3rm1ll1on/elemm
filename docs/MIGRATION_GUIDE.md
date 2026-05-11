# Migration Guide: Elemm v1.0.x → v1.1.0

This guide covers the key changes when migrating from Elemm v1.0.x to the v1.1.0 Landmark Manifest Protocol.

---

## What Changed in v1.1.0

Elemm v1.1.0 is a major feature release. The core protocol remains the same (landmarks, manifests, sequences), but a new **Gateway** has been added as a protocol-aware broker.

### Key Changes

| Area | v1.0.x | v1.1.0 |
|---|---|---|
| **Discovery** | Full manifest with all signatures upfront | Lazy loading: Manifest → Landmarks → Inspect on-demand |
| **Tool Exposure** | All tools leaked to MCP client | Only 8 core tools exposed. Domain tools via `call_action`. |
| **Multi-Protocol** | Native Elemm only | OpenAPI, GraphQL, and Native Elemm |
| **Security** | None | Guardian policy engine (patterns, landmarks, methods) |
| **Error Handling** | Basic exceptions | Structured `_PROTOCOL_ERROR` with SmartRepair and `_DEBUG_ECHO` |
| **Handshake** | Optional | Mandatory. `get_manifest()` must be called before execution. |
| **Sessions** | Global state | Isolated sessions via `session_id` |

---

## Step 1: Update Your Imports

The core API remains backward-compatible:

```python
# v1.0.x — still works
from elemm import ElemmGateway

# v1.1.0 — preferred
from elemm import AIProtocolManager, MetadataRegistry
```

`ElemmGateway` is still available as an alias for `AIProtocolManager`.

---

## Step 2: Use the Gateway for External APIs

In v1.0.x, connecting to external APIs required custom code. In v1.1.0, the built-in Gateway handles this. Just point your MCP client (like Claude Desktop) to the `elemm-gateway` command:

```json
{
  "mcpServers": {
    "elemm-gateway": {
      "command": "elemm-gateway"
    }
  }
}
```

The Gateway auto-detects OpenAPI specs, GraphQL endpoints, and native Elemm services when the agent connects.

---

## Step 3: Update Your Agent Prompts

The discovery protocol now has 5 mandatory steps:

1. `connect_to_site(url)` — Establish connection
2. `get_manifest()` — Authorize the session
3. `get_landmarks()` — Discover functional areas
4. `inspect_landmark(id)` — Get technical signatures
5. `call_action()` / `execute_sequence()` — Execute

> [!IMPORTANT]
> In v1.1.0, any action attempted before `get_manifest()` is rejected with `PROTOCOL_VIOLATION`. Ensure your agent's prompt instructs it to follow the discovery sequence.

---

## Step 4: Configure Security (Optional)

v1.1.0 introduces the Guardian security engine. Configure it in `~/.elemm/config.json`:

```json
{
  "security": {
    "disallowed_patterns": ["delete", "remove", "purge"],
    "disallowed_landmarks": ["admin"],
    "allowed_methods": ["GET", "POST"]
  }
}
```

See [Gateway Reference](GATEWAY.md) for the complete configuration schema.

---

## Step 5: Set Up Authentication (Optional)

For APIs requiring authentication, add entries to `~/.elemm/vault.json`:

```json
{
  "api.github.com": {
    "type": "bearer",
    "value": "ghp_your_token_here"
  }
}
```

The vault is automatically loaded on each `connect_to_site` call.

---

## Summary: What's Better?

1.  **No Tool Leakage**: Agents see exactly 8 tools, not hundreds.
2.  **Universal Connectivity**: OpenAPI and GraphQL support out of the box.
3.  **Security by Default**: Destructive operations are blocked without configuration.
4.  **Mandatory Protocol**: Prevents hallucination by enforcing the discovery sequence.
5.  **Session Isolation**: Parallel tasks no longer interfere with each other.
