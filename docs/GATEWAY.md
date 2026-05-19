# Elemm Gateway — Complete Reference

The Elemm Gateway is an autonomous MCP server that acts as a **protocol-aware broker** between AI agents and remote APIs. It enables any MCP-compatible client (Claude Desktop, Cursor, Anything LLM, etc.) to interact with **any OpenAPI, GraphQL, or native Elemm API** through a single, unified interface of **9 core tools**.

---

## Table of Contents

1. [Core Concepts](#1-core-concepts)
2. [Installation & Startup](#2-installation--startup)
3. [MCP Client Integration](#3-mcp-client-integration)
4. [The Mandatory Discovery Protocol](#4-the-mandatory-discovery-protocol)
5. [Core Tools Reference](#5-core-tools-reference)
6. [Multi-Protocol Support](#6-multi-protocol-support)
7. [Sequence Engine & Data Piping](#7-sequence-engine--data-piping)
8. [Response Hygiene](#8-response-hygiene)
9. [Security Policy (Guardian)](#9-security-policy-guardian)
10. [Vault — Authentication Management](#10-vault--authentication-management)
11. [Configuration Reference](#11-configuration-reference)
12. [SmartRepair — Error Guidance](#12-smartrepair--error-guidance)
13. [Protocol Error Codes](#13-protocol-error-codes)
14. [Architecture Overview](#14-architecture-overview)
15. [Dashboard & Observability](#15-dashboard--observability)

---

## 1. Core Concepts

The Gateway is built on three fundamental principles:

| Principle | Description |
|---|---|
| **Broker, Not Proxy** | The gateway never exposes raw API endpoints to the agent. It provides exactly 9 generic core tools. All domain-specific actions are accessed through `call_action` or `execute_sequence`. |
| **Manifest-Driven Discovery** | Agents must follow a strict handshake protocol (Connect -> Manifest -> Landmarks -> Inspect -> Execute) before they can run any action. This prevents hallucination and saves tokens. |
| **Token Hygiene** | Every response is truncated, filterable, and selectable. The gateway actively prevents context overflow in the AI agent's prompt window. |

---

## 2. Installation & Startup

### Prerequisites

- Python 3.10+
- The `elemm` core package

### Install

```bash
pip install elemm
```

### Run (STDIO — Recommended for MCP)

The CLI installs globally. Since it communicates via `stdio` by default, **you configure your MCP client to run it**, rather than running it manually in a terminal.

Example for Claude Desktop (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "elemm-gateway": {
      "command": "/absolute/path/to/project/.venv/bin/python3",
      "args": ["-m", "elemm_gateway.cli"]
    }
  }
}
```

*(If Claude cannot find the command, provide the absolute path to the `elemm-gateway` executable).*

### Run (SSE — For Web Clients)

```bash
python3 -m elemm_gateway.cli --transport sse --port 8000
```

### Run (BRIDGE — Universal USB Cable Mode 🔌)

To connect multiple stdio-only AI agents (e.g. Claude Desktop, Cursor, VS Code) to a single, central background Gateway (either running locally or containerized in Docker), you run the CLI in **Bridge Mode**. 

The CLI acts as a pure, lightweight bidrectional proxy that forwards the agent's stdio to the central SSE Gateway:

```bash
python3 -m elemm_gateway.cli --bridge http://localhost:8000/sse
```

This guarantees seamless **Multi-Agent Session Isolation** (each agent gets a unique `session_id`) and lets you access the central telemetry and example sandbox natively!

### CLI Options

| Flag | Default | Description |
|---|---|---|
| `url` (positional) | — | Optional URL to auto-connect on startup. |
| `--name` | `elemm-gateway` | Custom MCP server name. |
| `--verbose` | `false` | Enable debug-level logging to stderr. |
| `--transport` | `stdio` | Transport mechanism: `stdio` or `sse`. |
| `--host` | `0.0.0.0` | Host address for the SSE server. |
| `--port` | `8000` | Port for the SSE server. |
| `--bridge` | — | Target SSE server URL to bridge to (stdio <-> SSE tunnel). |

---

## 3. MCP Client Integration

### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "elemm-gateway": {
      "command": "/path/to/project/.venv/bin/python3",
      "args": ["-m", "elemm_gateway.cli"]
    }
  }
}
```

After configuring your client, you will see exactly **9 tools** registered:
`connect_to_site`, `get_manifest`, `get_landmarks`, `inspect_landmark`, `search_landmarks`, `call_action`, `execute_sequence`, `list_aliases`, `clear_session`.

---

## 4. The Mandatory Discovery Protocol

Every session must follow this strict sequence. The gateway enforces this via a **handshake mechanism**: any action attempted before `get_manifest` is called will be rejected with a `PROTOCOL_VIOLATION` error.

```
+-------------------------------------------------------------+
|  1. CONNECT        ->  connect_to_site(url)                  |
|  2. GET MANIFEST   ->  get_manifest()          [HANDSHAKE]   |
|  3. DISCOVER       ->  get_landmarks()                       |
|  4. INSPECT        ->  inspect_landmark(id)                  |
|  5. EXECUTE        ->  call_action() / execute_sequence()    |
+-------------------------------------------------------------+
```

### Handshake Enforcement

- On every `connect_to_site` call, the internal `manifest_loaded` flag is reset to `false`.
- The flag is set to `true` **only** when `get_manifest` is called.
- Any call to `call_action`, `execute_sequence`, or direct action names before the handshake will return:

```json
{
  "status": "error",
  "_PROTOCOL_ERROR": "PROTOCOL_VIOLATION",
  "message": "Protocol violation: You MUST call 'get_manifest' to receive system instructions before executing any actions.",
  "remedy": "Call 'get_manifest' immediately to authorize the session."
}
```

---

## 5. Core Tools Reference

### `connect_to_site`

Connects the gateway to a remote API. The gateway auto-detects the interface type (GraphQL, OpenAPI, or Native Elemm).

| Parameter | Type | Required | Description |
|---|---|---|---|
| `url` | `string` | Yes | URL of the API (e.g., an OpenAPI JSON, a GraphQL endpoint, or an Elemm site). |

**Auto-Detection Logic:**
1. If the URL contains `graphql` -> Attempts GraphQL introspection.
2. If the URL ends in `.json`, `.yaml`, `.yml`, or contains `/openapi` -> Parses as OpenAPI spec.
3. Otherwise -> Probes for a native Elemm manifest at `<url>/.well-known/elemm-manifest.md`.

### `get_manifest`

Returns the system instructions, protocol rules, landmark topology, and gateway globals for the active site. **This call authorizes the session** (completes the handshake).

| Parameter | Type | Required | Description |
|---|---|---|---|
| *(none)* | — | — | — |

### `get_landmarks`

Returns a high-level summary of available functional areas (landmarks) on the active site. Landmarks restricted by the Security Policy are automatically hidden.

| Parameter | Type | Required | Description |
|---|---|---|---|
| *(none)* | — | — | — |

**Example Output:**
```
### LANDMARK TOPOLOGY
- **repos**: (15 tools)
- **issues**: (8 tools)
- **git**: (12 tools)
```

### `inspect_landmark`

Returns TypeScript-style technical signatures for all tools within the specified landmark(s). This is the **ground truth** for parameter schemas.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `landmark_id` | `string` or `string[]` | Yes | One or more landmark IDs to inspect. |
| `_limit` | `integer` | No | Pagination limit to restrict the number of tools returned. |
| `_offset` | `integer` | No | Pagination offset to skip a number of tools/landmarks. |

**Example Output:**
```typescript
/**
 * Tool: repos_repos_get
 * Description: Get a repository
 * @param owner (string) [REQUIRED] The account owner of the repository
 * @param repo (string) [REQUIRED] The name of the repository
 */
function call_action(action: 'repos_repos_get', parameters: { owner: string, repo: string }): any;
```

> [!TIP]
> Always call `inspect_landmark` before executing actions. Guessing parameter names or schemas from memory is the #1 cause of agent failures.

### `search_landmarks`

Global Python REGEX search over all landmarks and individual actions. Returns executable actions directly, bypassing the full hierarchy navigation.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `query` | `string` | Yes | Regex pattern (e.g. `'repos\|issues'` or `'^security:.*'`). |
| `_limit` | `integer` | No | Max number of results to return (defaults to a safe context-hygiene cap of 10 if not specified). |
| `_offset` | `integer` | No | Starting index for pagination. |

> [!NOTE]
> **Context-Hygiene & Scale Protection**:
> To protect the agent's context window from being overloaded in large environments (e.g. 100k+ tools), the following behaviors are enforced:
> 1. **Default Cap**: Large query results are automatically capped at 10 items.
> 2. **Truncation Warning**: If there are more results than the limit, a detailed warning notice is injected showing the total count of matches.
> 3. **Dynamic Namespace Suggestion**: The response dynamically recommends narrowing the search area by utilizing the specific namespace of the first matching landmark as a filter inside a follow-up `get_manifest(landmark_id="...")` call (e.g. `get_manifest(landmark_id="Zentrum:Sector_042:energy")`).

### `call_action`

Executes a single action on the remote site.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `action` | `string` | Yes | The Action ID to execute (e.g., `repos_repos_get`). |
| `parameters` | `object` | No | Parameters for the action. |

### `execute_sequence`

Executes multiple actions in a single turn with data piping between steps. See [Section 7](#7-sequence-engine--data-piping) for full details.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `actions` | `array` | Yes | List of step objects (see below). |
| `steps` | `array` | — | Alias for `actions` (accepted for LLM flexibility). |
| `session_id` | `string` | No | Session ID for memory isolation. Default: `"default"`. |

**Step Object:**

| Field | Type | Required | Description |
|---|---|---|---|
| `action` | `string` | Yes | The Action ID to execute. |
| `alias` | `string` | No | Custom alias for this step's result (e.g., `"my_repos"`). Defaults to `stepN`. |
| `parameters` | `object` | No | Parameters. Supports `$alias.path` piping syntax. |
| `on_error` | `"stop"` or `"continue"` | No | Error handling strategy. Default: `"stop"`. |
| `retry` | `integer` | No | Number of retry attempts. Default: `0`. |
| `retryOn` | `string[]` | No | List of `_PROTOCOL_ERROR` codes that trigger a retry (e.g., `["RATE_LIMIT_EXCEEDED"]`). |

### `list_aliases`

Returns all stored aliases (results from previous sequence steps) for a given session.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `session_id` | `string` | No | The session to inspect. Default: `"default"`. |

### `clear_session`

Clears all stored aliases and pipeline state for a session. Use for privacy and memory hygiene.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `session_id` | `string` | No | The session to clear. Default: `"default"`. |

---

## 6. Multi-Protocol Support

The gateway seamlessly bridges three API paradigms into the unified Elemm discovery model.

### OpenAPI (REST)

- **Detection:** URL ending in `.json`, `.yaml`, `.yml`, or containing `/openapi`.
- **Supported Versions:** OpenAPI 3.x and Swagger 2.0.
- **Feature Coverage:**
  - Path, query, header, and body parameters.
  - Path-level parameter inheritance.
  - `$ref` resolution for component parameters.
  - `requestBody` schema flattening.
  - Server URL extraction (with relative URL handling).
  - Security scheme detection with vault integration warnings.
  - Tag-based landmark grouping with metadata descriptions.
  - **Custom Directives (`x-elemm-instructions`)**: Automatic extraction of custom behavioral guidelines from the OpenAPI `info` block or root level, injecting them directly into the transient session manifest as system instructions.

### GraphQL

- **Detection:** URL containing the keyword `graphql`.
- **Discovery:** Automatic introspection via the standard `__schema` query.
- **Feature Coverage:**
  - Query and Mutation field extraction.
  - Argument type mapping (Scalars, Lists, NonNull, InputObjects).
  - Automatic GQL type annotations preserved in tool metadata (`gql_type`).
  - Dynamic `_select` parameter for controlling the selection set.
  - Nested field selection via dot-notation (e.g., `_select: "name, info.id"`).
  - Automatic variable generation and type-safe query construction.

### Native Elemm

- **Detection:** Falls back to probing `<url>/.well-known/elemm-manifest.md`.
- **Feature Coverage:**
  - Lazy manifest loading (no tool signatures at connect time).
  - On-demand landmark inspection via the remote server.
  - Proxy execution via the standard `/.well-known/elemm/execute` endpoint.

---

## 7. Sequence Engine & Data Piping

The `execute_sequence` tool is the gateway's most powerful feature. It allows agents to batch multiple API calls into a single LLM turn, dramatically reducing token consumption and latency.

### Data Piping Syntax

Results from each step are stored as aliases and can be referenced in subsequent steps:

| Syntax | Description | Example |
|---|---|---|
| `$stepN` | Access result of step N (0-indexed). | `$step0` |
| `$alias` | Access result by custom alias. | `$my_repos` |
| `$alias.field` | Access a nested field. | `$step0.name` |
| `$alias.deep.path` | Deep nested access. | `$step0.owner.login` |
| `$alias[N]` | Array indexing. | `$step0[0]` |
| `$alias[N].field` | Array index + field access. | `$step0[0].id` |

### Error Handling Strategies

| `on_error` | Behavior |
|---|---|
| `"stop"` (default) | Halts the entire sequence on error. Subsequent steps are skipped. |
| `"continue"` | Logs the error, stores it in the alias, and proceeds to the next step. |

### Smart Retry

Steps can be configured to automatically retry on specific error types:

```json
{
  "action": "api_get_data",
  "retry": 3,
  "retryOn": ["RATE_LIMIT_EXCEEDED", "SERVER_ERROR"],
  "parameters": {}
}
```

The engine waits 1 second between retries (basic backoff).

### Example: Multi-Step Pipeline

```json
{
  "actions": [
    {
      "action": "repos_repos_list-for-user",
      "alias": "repos",
      "parameters": {"username": "v3rm1ll1on", "_limit": 5}
    },
    {
      "action": "repos_repos_get",
      "alias": "detail",
      "parameters": {"owner": "v3rm1ll1on", "repo": "$repos[0].name"}
    }
  ],
  "session_id": "my_task"
}
```

### Session Isolation

Each `session_id` maintains its own isolated memory bank. This allows parallel tasks to run without cross-contamination. Always call `clear_session` after completing a task.

---

## 8. Response Hygiene

Every action call supports four universal hygiene parameters that are processed **gateway-side** before the response reaches the agent:

| Parameter | Type | Description |
|---|---|---|
| `_select` | `string` | Comma-separated list of fields to return. Supports dot-notation for nested objects (e.g., `"name, owner.login"`). |
| `_filter` | `string` or `object` | Equality filter applied to array responses (e.g., `"state=open"` or `{"state": "open"}`). |
| `_limit` | `integer` | Maximum number of items to return from array responses. |
| `_offset` | `integer` | Number of items to skip (pagination). |

### Truncation Limits

Responses are automatically truncated to prevent context overflow:

| Context | Default Limit | Config Key |
|---|---|---|
| Standard responses | 30,000 characters | `limit_standard` |
| Inspection responses | 20,000 characters | `limit_inspect` |

When truncation occurs, the agent receives a hint:
```
(Note: Result truncated to prevent context overflow. Use '_select' or '_limit' for better hygiene.)
```

---

## 9. Security Policy (Guardian)

The gateway includes a built-in security engine ("Guardian") that enforces restrictions **before** any request reaches the target API. All policies are configured in `~/.elemm/config.json`.

### Policy Layers

Policies are evaluated in this order. The first match blocks the action.

| Layer | Config Key | Description |
|---|---|---|
| **Zero-Trust Whitelist** | `enforce_whitelist` + `allowed_landmarks/actions` | When `enforce_whitelist: true`, only explicitly listed actions/landmarks are permitted. All others are denied. |
| **HTTP Method Restriction** | `allowed_methods` | Whitelist of allowed HTTP methods. An empty list (`[]`) means **all methods are allowed**. |
| **Action Blacklist** | `disallowed_actions` | Exact action IDs to block (e.g., `["admin_delete-user"]`). |
| **Landmark Blacklist** | `disallowed_landmarks` | Entire landmark namespaces to hide and block (e.g., `["admin", "billing"]`). |
| **Pattern Matching** | `disallowed_patterns` | Substrings that trigger blocking. Prefix with `re:` for full Python regex (e.g., `["re:.*secret.*", "delete"]`). |
| **Deep Argument Inspection** | `disallowed_patterns` | Pattern matching is applied **recursively** to all argument values, not just the action name. |
| **Data Loss Prevention** | `prevent_key_leakage` | When `true` (default), vault API keys are automatically scrubbed from all responses before reaching the agent. |

### Discovery Filtering

Blocked landmarks are **invisible** to the agent. They do not appear in `get_landmarks` output, and `inspect_landmark` will refuse to show their signatures.

### Response Format

When a policy violation occurs:
```json
{
  "status": "error",
  "_PROTOCOL_ERROR": "ACCESS_DENIED",
  "message": "Action contains restricted pattern 'delete'.",
  "remedy": "Destructive operations are disabled by default. Use read-only or safe alternatives."
}
```

### Exempt Actions

The following are always exempt from security checks:
- All 9 core tools (`connect_to_site`, `get_manifest`, `get_landmarks`, `inspect_landmark`, `search_landmarks`, `call_action`, `execute_sequence`, `list_aliases`, `clear_session`)
- Internal `elemm:` prefixed actions

---

## 10. Vault — Authentication Management

The gateway manages API keys and tokens via a local vault file at `~/.elemm/vault.json`. Credentials are automatically injected into outgoing requests based on the target API's hostname.

### Vault File Format (`~/.elemm/vault.json`)

```json
{
  "api.github.com": {
    "type": "bearer",
    "value": "ghp_your_personal_access_token"
  },
  "api.openweathermap.org": {
    "type": "apiKey",
    "name": "appid",
    "in": "query",
    "value": "your_api_key_here"
  },
  "api.stripe.com": {
    "type": "bearer",
    "value": "sk_test_51Mz..."
  },
  "custom.internal.api": {
    "type": "apiKey",
    "name": "X-Auth-Token",
    "in": "header",
    "value": "secret-123"
  },
  "legacy-service.com": {
    "type": "basic",
    "value": "dXNlcjpwYXNzd29yZA=="
  }
}
```

### Supported Auth Types

| Type | Header/Param Behavior |
|---|---|
| `apiKey` | Injects as query parameter or header (controlled by `in` field). |
| `bearer` | Sets `Authorization: Bearer <value>` header. |
| `basic` | Sets `Authorization: Basic <value>` header. |
| *(string shorthand)* | A plain string value is treated as `apiKey` with `name: "key"` in query. |

### Auth-Aware Validation

The gateway's pre-validation engine is **vault-aware**: if a required parameter (e.g., `appid`) is provided by the vault, it will not be flagged as "missing" during local validation.

### Auto-Reload

The vault is re-read from disk on every `connect_to_site` call. There is no need to restart the gateway after editing `vault.json`.

### Missing Auth Warning

If the target API defines security schemes (in its OpenAPI spec) and no matching vault entry exists, the gateway emits a warning during connection:
```
[WARNING]
AUTHENTICATION REQUIRED: This site requires apiKey.
REMEDY: Add an entry for 'api.example.com' to your `~/.elemm/vault.json`.
INSTRUCTION: Inform the user that an API key is required for this service.
```

---

## 11. Configuration Reference

The gateway is configured via `~/.elemm/config.json`. The file is auto-created with sensible defaults on first run. Missing keys are auto-migrated.

### Full Schema

```json
{
  "security": {
    "enforce_whitelist": false,
    "allowed_landmarks": [],
    "allowed_actions": [],
    "disallowed_patterns": ["delete", "remove", "purge", "destroy"],
    "disallowed_landmarks": ["admin", "billing", "internal"],
    "disallowed_actions": ["users_delete_account"],
    "allowed_methods": ["GET", "POST", "PUT", "PATCH", "DELETE"],
    "prevent_key_leakage": true,
    "custom_remedies": {},
    "simulate_security_policy": false
  },
  "limit_standard": 30000,
  "limit_inspect": 20000,
  "limit_search_items": 10,
  "timeout_seconds": 30,
  "retry_attempts": 3,
  "retry_delay_ms": 1000,
  "max_tools_per_landmark": 5,
  "max_landmarks_per_view": 20,
  "user_agent": "ElemmGateway/1.0 (Autonomous Agent)",
  "ui": {
    "display_mode": "tokens",
    "char_to_token_ratio": 4.0,
    "simulate_security_policy": false
  }
}
```

### Key Reference

| Key | Type | Default | Description |
|---|---|---|---|
| `security.enforce_whitelist` | `boolean` | `false` | Zero-Trust mode. Only listed landmarks/actions are permitted. |
| `security.allowed_landmarks` | `string[]` | `[]` | Whitelisted landmark namespaces (Zero-Trust mode only). |
| `security.allowed_actions` | `string[]` | `[]` | Whitelisted exact action IDs (Zero-Trust mode only). |
| `security.disallowed_patterns` | `string[]` | `["delete", "remove", "purge", "destroy"]` | Action name substrings to block. Prefix with `re:` for regex. |
| `security.disallowed_landmarks` | `string[]` | `[]` | Landmark namespaces to hide and block entirely. |
| `security.disallowed_actions` | `string[]` | `[]` | Explicit action IDs to block. |
| `security.allowed_methods` | `string[]` | `["GET","POST","PUT","PATCH","DELETE"]` | Whitelisted HTTP methods. |
| `security.prevent_key_leakage` | `boolean` | `true` | Scrub vault API keys from all agent responses. |
| `security.custom_remedies` | `object` | `{}` | Map of `pattern/action_id` → custom remedy message. |
| `limit_standard` | `integer` | `30000` | Max characters for standard responses. |
| `limit_inspect` | `integer` | `20000` | Max characters for inspection responses. |
| `limit_search_items` | `integer` | `10` | Max results for `search_landmarks`. |
| `timeout_seconds` | `integer` | `30` | HTTP request timeout. |
| `retry_attempts` | `integer` | `3` | Default retry count for transient failures. |
| `retry_delay_ms` | `integer` | `1000` | Delay between retries in milliseconds. |
| `max_tools_per_landmark` | `integer` | `5` | Max tools shown per landmark on connect. |
| `max_landmarks_per_view` | `integer` | `20` | Max landmarks shown in `get_landmarks`. |
| `user_agent` | `string` | `"ElemmGateway/1.0"` | User-Agent header for outgoing HTTP requests. |

---

## 12. SmartRepair — Error Guidance

The gateway never returns raw stack traces or cryptic HTTP errors. Every error is wrapped in a structured `RepairResult` containing:

- **`message`**: A clear, human-readable explanation.
- **`remedy`**: Actionable instructions for the agent to self-correct.
- **`_DEBUG_ECHO`**: A forensic payload showing exactly what was sent (method, URL, parameters).

### Namespace Execution Prevention

If an agent tries to execute a landmark namespace directly (e.g., `call_action(action="repos")` instead of a specific tool like `repos_repos_get`), the SmartRepair engine intercepts this and returns guidance:
```
"You attempted to call a landmark namespace, not a specific action.
 Use 'inspect_landmark' to discover available actions within this namespace."
```

### Fuzzy Matching

If an action ID is not found, the engine performs fuzzy matching against all registered tools and suggests the closest matches.

---

## 13. Protocol Error Codes

All errors returned by the gateway follow a standardized format with a `_PROTOCOL_ERROR` field.

| Code | HTTP Equivalent | Description |
|---|---|---|
| `PROTOCOL_VIOLATION` | — | Agent attempted action before completing the handshake. |
| `ACCESS_DENIED` | 403 | Blocked by Security Policy or remote API. |
| `AUTHENTICATION_FAILED` | 401 | Missing or invalid API credentials. |
| `NOT_FOUND` | 404 | Action or resource not found on the remote API. |
| `VALIDATION_FAILED` | 422 | Missing required parameters (caught locally). |
| `BAD_REQUEST` | 400 | Malformed request to the remote API. |
| `RATE_LIMIT_EXCEEDED` | 429 | API rate limit hit. |
| `SERVER_ERROR` | 500 | Remote API internal server error. |
| `REMOTE_ERROR` | Other | Unmapped HTTP error from the remote API. |
| `PIPING_FAILED` | — | Data piping reference could not be resolved in sequence. |
| `GRAPHQL_ERROR` | — | GraphQL-specific query error. |
| `NESTING_REQUIRED` | — | GraphQL field requires sub-field selection. |
| `TYPE_MISMATCH` | — | GraphQL variable type does not match schema. |

---

## 14. Architecture Overview

```
+----------------------------------------------------------------------+
|                        MCP CLIENT (Agent)                            |
|              (Claude Desktop / Cursor / Anything LLM)                |
+----------------------------+-----------------------------------------+
                             |  9 Core Tools (MCP Protocol)
                             ▼
+----------------------------------------------------------------------+
|                    ELEMM GATEWAY (server.py)                         |
|                                                                      |
|  +--------------+  +---------------+  +──────────────────────────+  |
|  |SecurityPolicy|  |ManifestService|  |   ConfigManager          |  |
|  |  (Guardian)  |  |               |  |   (~/.elemm/config.json) |  |
|  +--------------+  +---------------+  +──────────────────────────+  |
|                                                                      |
|  +--------------+  +---------------+  +──────────────────────────+  |
|  | VaultManager |  | SequenceEngine|  |   ResponseSquisher       |  |
|  | (~/.elemm/   |  | (Piping,      |  |   (_select, _filter,     |  |
|  |  vault.json) |  |  Sessions,    |  |    _limit, _offset)      |  |
|  |              |  |  Retry)       |  |                          |  |
|  +--------------+  +---------------+  +──────────────────────────+  |
|                                                                      |
|  +──────────────────────────────────────────────────────────────+    |
|  |               Protocol Bridges                               |    |
|  |  +--------------+  +---------------+  +────────────────+    |    |
|  |  | OpenAPIBridge |  | GraphQLBridge  |  | Native Elemm   |    |    |
|  |  |  (REST/JSON)  |  |(Introspection)|  | (Manifest .md) |    |    |
|  |  +──────┬───────+  +───────┬───────+  +───────┬────────+    |    |
|  +─────────┼──────────────────┼──────────────────┼──────────────+    |
|            |  ActivityMonitor (telemetry -> Dashboard)                |
+------------┼──────────────────┼──────────────────┼───────────────────+
             |                  |                  |
             ▼                  ▼                  ▼
    +----------------+  +--------------+  +------------------+
    |  OpenAPI APIs   |  | GraphQL APIs |  |  Elemm Servers   |
    |  (GitHub, etc.) |  |              |  |  (Smart Home,..) |
    +----------------+  +--------------+  +------------------+
```

### Component Responsibilities

| Component | File | Responsibility |
|---|---|---|
| `ElemmGateway` | `server.py` | Main dispatcher, connection manager, handshake enforcement, telemetry. |
| `ManifestService` | `services/manifest_service.py` | URL probing, bridge routing, landmark inspection, manifest generation. |
| `SecurityPolicy` | `services/security.py` | Full Guardian engine: whitelist, blacklist, patterns, DLP, argument inspection. |
| `ConfigManager` | `services/config.py` | Loads `~/.elemm/config.json` with hot-reload on every request. |
| `VaultManager` | `services/vault.py` | Loads `~/.elemm/vault.json` and injects auth headers into outgoing requests. |
| `ResponseSquisher` | `services/hygiene.py` | Applies `_select`, `_filter`, `_limit`, `_offset` hygiene to responses. |
| `SequenceEngine` | `services/sequencer.py` | Executes multi-step pipelines with piping, retry, and session isolation. |
| `OpenAPIExecutor` | `services/executors.py` | Constructs and sends HTTP requests for OpenAPI-based actions. |
| `GraphQLExecutor` | `services/executors.py` | Constructs GQL queries with variables and executes them. |
| `OpenAPIBridge` | `services/openapi_bridge.py` | Parses OpenAPI/Swagger specs into Elemm landmark registries. |
| `GraphQLBridge` | `services/graphql_bridge.py` | Parses GraphQL introspection data into Elemm landmark registries. |
| `GatewayToolRegistry` | `services/tool_registry.py` | Defines the 9 core MCP tool schemas. |
| `ActivityMonitor` | `services/monitor.py` | Publishes telemetry events to the Dashboard backend. |
| `CLI` | `cli.py` | Entry point with argument parsing and stdio/sse transport selection. |

---

## File Locations

| File | Path |
|---|---|
| Gateway Configuration | `~/.elemm/config.json` |
| Authentication Vault | `~/.elemm/vault.json` |
| Example Security Config | `examples/security_config_example.json` |
| Gateway Source | `src/elemm_gateway/` |
| Test Suite | `tests/` |
