# Elemm Gateway v2 — Complete Reference

The Elemm Gateway is an autonomous MCP server that acts as a **protocol-aware broker** between AI agents and remote APIs. It enables any MCP-compatible client (Claude Desktop, Cursor, Anything LLM, etc.) to interact with **any OpenAPI, GraphQL, or native Elemm API** through a single, unified interface of just 8 core tools.

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

---

## 1. Core Concepts

The Gateway is built on three fundamental principles:

| Principle | Description |
|---|---|
| **Broker, Not Proxy** | The gateway never exposes raw API endpoints to the agent. It provides exactly 8 generic core tools. All domain-specific actions are accessed through `call_action` or `execute_sequence`. |
| **Manifest-Driven Discovery** | Agents must follow a strict handshake protocol (Connect → Manifest → Landmarks → Inspect → Execute) before they can run any action. This prevents hallucination and saves tokens. |
| **Token Hygiene** | Every response is truncated, filterable, and selectable. The gateway actively prevents context overflow in the AI agent's prompt window. |

---

## 2. Installation & Startup

### Prerequisites

- Python 3.10+
- The `elemm` core package
- The `elemm-gateway` package (this repository)

### Install

```bash
pip install elemm
```

### Run (STDIO — Recommended for MCP)

```bash
elemm-gateway
```

### Run (SSE — For Web Clients)

```bash
PYTHONPATH=src python3 -m elemm_gateway.cli --transport sse --port 8000
```

### CLI Options

| Flag | Default | Description |
|---|---|---|
| `url` (positional) | — | Optional URL to auto-connect on startup. |
| `--name` | `elemm-gateway` | Custom MCP server name. |
| `--verbose` | `false` | Enable debug-level logging to stderr. |
| `--transport` | `stdio` | Transport mechanism: `stdio` or `sse`. |
| `--host` | `0.0.0.0` | Host address for the SSE server. |
| `--port` | `8000` | Port for the SSE server. |

---

## 3. MCP Client Integration

### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "elemm-gateway": {
      "command": "python3",
      "args": ["-m", "elemm_gateway.cli"],
      "env": {
        "PYTHONPATH": "/path/to/ai_landmarks_pkg/src"
      }
    }
  }
}
```

### Anything LLM / Cursor (WSL Example)

```
Command:  wsl.exe
Args:     -u <user> -d Ubuntu bash -c "cd /path/to/ai_landmarks_pkg && PYTHONPATH=src ./venv/bin/python3 -m elemm_gateway.cli"
```

After configuring your client, you will see exactly **8 tools** registered:
`connect_to_site`, `get_manifest`, `call_action`, `execute_sequence`, `get_landmarks`, `inspect_landmark`, `list_aliases`, `clear_session`.

> [!IMPORTANT]
> If you see more than 8 tools (e.g., hundreds of API-specific tools), you are running an outdated version of the gateway. The gateway **never** exposes domain-specific tools to the MCP client. All actions are routed through `call_action` and `execute_sequence`.

---

## 4. The Mandatory Discovery Protocol

Every session must follow this strict sequence. The gateway enforces this via a **handshake mechanism**: any action attempted before `get_manifest` is called will be rejected with a `PROTOCOL_VIOLATION` error.

```
┌─────────────────────────────────────────────────────────────┐
│  1. CONNECT        →  connect_to_site(url)                  │
│  2. GET MANIFEST   →  get_manifest()          [HANDSHAKE]   │
│  3. DISCOVER       →  get_landmarks()                       │
│  4. INSPECT        →  inspect_landmark(id)                  │
│  5. EXECUTE        →  call_action() / execute_sequence()    │
└─────────────────────────────────────────────────────────────┘
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
1. If the URL contains `graphql` → Attempts GraphQL introspection.
2. If the URL ends in `.json`, `.yaml`, `.yml`, or contains `/openapi` → Parses as OpenAPI spec.
3. Otherwise → Probes for a native Elemm manifest at `<url>/.well-known/elemm-manifest.md`.

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

Every action call supports three universal hygiene parameters that are processed **gateway-side** before the response reaches the agent:

| Parameter | Type | Description |
|---|---|---|
| `_select` | `string` | Comma-separated list of fields to return. Supports dot-notation for nested objects (e.g., `"name, owner.login"`). |
| `_filter` | `string` or `object` | Equality filter applied to array responses (e.g., `"state=open"` or `{"state": "open"}`). |
| `_limit` | `integer` | Maximum number of items to return from array responses. |

### Truncation Limits

Responses are automatically truncated to prevent context overflow:

| Context | Default Limit | Config Key |
|---|---|---|
| Standard responses | 5,000 characters | `limit_standard` |
| Inspection responses | 20,000 characters | `limit_inspect` |

When truncation occurs, the agent receives a hint:
```
(Note: Result truncated to prevent context overflow. Use '_select' or '_limit' for better hygiene.)
```

---

## 9. Security Policy (Guardian)

The gateway includes a built-in security engine ("Guardian") that enforces restrictions **before** any request reaches the target API. All policies are configured in `~/.elemm/config.json`.

### Policy Layers

Policies are evaluated in order. The first match blocks the action.

| Layer | Config Key | Description |
|---|---|---|
| **HTTP Method Restriction** | `allowed_methods` | Whitelist of allowed HTTP methods. An empty list (`[]`) means **all methods are allowed**. |
| **Action Blacklist** | `disallowed_actions` | Exact action IDs to block (e.g., `["admin_delete-user"]`). |
| **Landmark Blacklist** | `disallowed_landmarks` | Entire landmark namespaces to hide and block (e.g., `["admin", "billing"]`). |
| **Pattern Matching** | `disallowed_patterns` | Substrings that trigger blocking if found in the action ID (e.g., `["delete", "remove", "purge"]`). |

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
- All core tools (`connect_to_site`, `get_manifest`, `get_landmarks`, etc.)
- Internal `elemm:` prefixed actions
- Inspection actions (ending in `_inspect`)

### Example Configuration

See [`examples/security_config_example.json`](../examples/security_config_example.json) for a production-ready template.

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
  "internal.corp.com": {
    "type": "basic",
    "value": "base64_encoded_user:password"
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
    "disallowed_patterns": ["delete", "remove", "purge", "destroy"],
    "disallowed_landmarks": [],
    "disallowed_actions": [],
    "allowed_methods": ["GET", "POST", "PUT", "PATCH", "DELETE"]
  },
  "limit_standard": 5000,
  "limit_inspect": 20000,
  "timeout_seconds": 30,
  "retry_attempts": 3,
  "retry_delay_ms": 1000
}
```

### Key Reference

| Key | Type | Default | Description |
|---|---|---|---|
| `security.disallowed_patterns` | `string[]` | `["delete", "remove", "purge", "destroy"]` | Action name substrings to block. |
| `security.disallowed_landmarks` | `string[]` | `[]` | Landmark namespaces to hide and block entirely. |
| `security.disallowed_actions` | `string[]` | `[]` | Explicit action IDs to block. |
| `security.allowed_methods` | `string[]` | `["GET", "POST", "PUT", "PATCH", "DELETE"]` | Whitelisted HTTP methods. Empty `[]` = all allowed. |
| `limit_standard` | `integer` | `5000` | Max characters for standard responses. |
| `limit_inspect` | `integer` | `20000` | Max characters for inspection responses. |
| `timeout_seconds` | `integer` | `30` | HTTP request timeout. |
| `retry_attempts` | `integer` | `3` | Default retry count for transient failures. |
| `retry_delay_ms` | `integer` | `1000` | Delay between retries in milliseconds. |

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
┌──────────────────────────────────────────────────────────────────────┐
│                        MCP CLIENT (Agent)                            │
│              (Claude Desktop / Cursor / Anything LLM)                │
└────────────────────────────┬─────────────────────────────────────────┘
                             │  8 Core Tools (MCP Protocol)
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│                       ELEMM GATEWAY v2                               │
│                                                                      │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────────────────┐  │
│  │ SecurityPolicy│  │ManifestBuilder│  │   ConfigManager          │  │
│  │  (Guardian)   │  │               │  │   (~/.elemm/config.json) │  │
│  └──────────────┘  └───────────────┘  └──────────────────────────┘  │
│                                                                      │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────────────────┐  │
│  │ VaultManager │  │SequenceEngine │  │   ResponseSquisher       │  │
│  │ (~/.elemm/   │  │ (Piping,      │  │   (_select, _filter,     │  │
│  │  vault.json) │  │  Sessions,    │  │    _limit, Truncation)   │  │
│  │              │  │  Retry)       │  │                          │  │
│  └──────────────┘  └───────────────┘  └──────────────────────────┘  │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │               Protocol Bridges                               │    │
│  │  ┌──────────────┐  ┌───────────────┐  ┌────────────────┐    │    │
│  │  │ OpenAPIBridge │  │ GraphQLBridge  │  │ Native Elemm   │    │    │
│  │  │  (REST/JSON)  │  │(Introspection)│  │ (Manifest .md) │    │    │
│  │  └──────┬───────┘  └───────┬───────┘  └───────┬────────┘    │    │
│  └─────────┼──────────────────┼──────────────────┼──────────────┘    │
└────────────┼──────────────────┼──────────────────┼───────────────────┘
             │                  │                  │
             ▼                  ▼                  ▼
    ┌────────────────┐  ┌──────────────┐  ┌──────────────────┐
    │  OpenAPI APIs   │  │ GraphQL APIs │  │  Elemm Servers   │
    │  (GitHub, etc.) │  │              │  │  (Smart Home,..) │
    └────────────────┘  └──────────────┘  └──────────────────┘
```

### Component Responsibilities

| Component | File | Responsibility |
|---|---|---|
| `ElemmGateway` | `server.py` | Main dispatcher, connection manager, handshake enforcement. |
| `ManifestBuilder` | `components.py` | Generates and injects protocol rules, globals, and memory bank instructions. |
| `SecurityPolicy` | `components.py` | Enforces pattern, landmark, action, and HTTP method restrictions. |
| `ConfigManager` | `components.py` | Loads, migrates, and provides access to `~/.elemm/config.json`. |
| `VaultManager` | `components.py` | Loads `~/.elemm/vault.json` and injects auth into outgoing requests. |
| `ResponseSquisher` | `components.py` | Applies `_select`, `_filter`, and `_limit` hygiene to responses. |
| `SequenceEngine` | `components.py` | Executes multi-step pipelines with piping, retry, and session isolation. |
| `OpenAPIExecutor` | `components.py` | Constructs and sends HTTP requests for OpenAPI-based actions. |
| `GraphQLExecutor` | `components.py` | Constructs GQL queries with variables and executes them. |
| `OpenAPIBridge` | `openapi_bridge.py` | Parses OpenAPI/Swagger specs into Elemm tool registries. |
| `GraphQLBridge` | `graphql_bridge.py` | Parses GraphQL introspection data into Elemm tool registries. |
| `CLI` | `cli.py` | Entry point with argument parsing, transport selection, and banner. |

---

## File Locations

| File | Path |
|---|---|
| Gateway Configuration | `~/.elemm/config.json` |
| Authentication Vault | `~/.elemm/vault.json` |
| Example Security Config | `examples/security_config_example.json` |
| Gateway Source | `src/elemm_gateway/` |
| Test Suite | `tests/` |
