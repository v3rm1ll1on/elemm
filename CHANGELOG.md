# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.1] - 2026-05-11

### Fixed
- **Documentation**: Clarified that the `elemm-gateway` CLI is intended to be run by MCP clients (like Claude Desktop or Cursor), not manually via the terminal, to avoid confusion with the default STDIO transport.

## [1.1.0] - 2026-05-11

### Added
- **Elemm Gateway**: Universal MCP server that acts as a protocol-aware broker between AI agents and remote APIs.
- **OpenAPI Bridge**: Automatic parsing of OpenAPI 3.x and Swagger 2.0 specifications into Elemm landmarks, including path parameters, `$ref` resolution, `requestBody` flattening, and server URL extraction.
- **GraphQL Bridge**: Automatic introspection and mapping of GraphQL endpoints to Elemm landmarks, with type-safe variable generation and nested `_select` field support.
- **Security Policy Engine (Guardian)**: Multi-layer security with pattern blacklists (`delete`, `remove`, `purge`), landmark restrictions, explicit action blocks, and HTTP method filtering.
- **Vault Manager**: Local credential management (`~/.elemm/vault.json`) supporting `apiKey`, `bearer`, and `basic` authentication, with auto-injection and vault-aware validation.
- **Mandatory Handshake Protocol**: `get_manifest()` must be called before any action execution. Violations return `PROTOCOL_VIOLATION`.
- **Broker Isolation**: The gateway exposes exactly 8 core tools to MCP clients. Domain-specific tools are never leaked, preventing context pollution.
- **Response Hygiene**: Universal `_select`, `_filter`, and `_limit` parameters on all actions, with configurable truncation limits.
- **Session Isolation**: `session_id` parameter for parallel task isolation with `list_aliases` and `clear_session` for memory management.
- **Smart Retry**: Per-step `retry` count and `retryOn` error codes in `execute_sequence`.
- **Structured Error Responses**: All errors include `_PROTOCOL_ERROR`, `message`, `remedy`, and `_DEBUG_ECHO` for forensic debugging.
- **Namespace Execution Prevention**: SmartRepair intercepts attempts to call landmark namespaces directly and provides guidance.
- **Fuzzy Matching**: Suggests closest matching action IDs when an unknown action is called.
- **SSE Transport**: Optional `--transport sse` mode for web-based MCP clients.
- **CLI Entry Point**: `elemm-gateway` command registered via `pyproject.toml` for zero-config startup.
- **Configuration Manager**: Auto-created `~/.elemm/config.json` with sensible defaults and automatic migration of missing keys.
- **Complete Documentation Suite**: GATEWAY.md (full reference), updated ARCHITECTURE.md, PROTOCOL_SPEC.md, GETTING_STARTED.md, DEVELOPER_GUIDE.md, and MIGRATION_GUIDE.md.

### Changed
- **Discovery Protocol**: Expanded from 3-stage to 5-stage mandatory sequence (Connect → Manifest → Landmarks → Inspect → Execute).
- **Tool Registration**: Gateway `list_tools` returns only core tools, never domain-specific endpoints from connected APIs.
- **Manifest Generation**: Lazy loading architecture — tool signatures are not included in the manifest. Agents must use `inspect_landmark` for on-demand technical discovery.
- **Error Format**: Unified `_PROTOCOL_ERROR` codes across all bridges (OpenAPI, GraphQL, Native) with HTTP status code mapping.

### Fixed
- **Tool Leakage**: Removed legacy code that exposed all parsed API endpoints as native MCP tools to the client.
- **Allow-All Policy Bug**: Empty `allowed_methods` list now correctly means "all methods allowed" instead of "no methods allowed".
- **User-Agent Header**: All outgoing HTTP requests now include `User-Agent: Elemm-Gateway/2.0`.

## [1.0.2] - 2026-05-08

### Added
- **Practical Migration Guide**: New hands-on guide for shifting existing APIs and tools from Classic MCP to Elemm.
- **Visionary Documentation**: Expanded README with the 'Agentic Web' and 'Decoupled Intelligence' philosophy.
- **Dynamic Gateway Pattern**: Documented the architectural pattern for scaling with distributed microservices.

### Fixed
- **Documentation Leaks**: Harmonized code examples across all guides to follow a consistent Cloud Infrastructure narrative.
- **Reference Models**: Updated benchmark references to gemma4:e2b.

## [1.0.1] - 2026-05-08

### Added
- **Pydantic Smart Unboxing**: Automatic expansion of single Pydantic model arguments into individual tool parameters for improved agent interaction.
- **Hierarchical Remedies**: Implemented remedy inheritance where tools can automatically use global remedies defined at the landmark level.
- **Declarative YAML Reference**: Added comprehensive schema documentation for `landmarks.yaml` configuration.
- **Extended Registry Support**: Added support for YAML aliases like `remedy_global` and explicit `configure_landmark` programmatic API.

### Changed
- **Branding Update**: Rebranded the protocol to **Elemm: The Landmark Manifest Protocol**.
- **Documentation Overhaul**: Professionalized all documentation files and improved layout consistency.
- **API Refinement**: Introduced `ElemmGateway` as the primary high-level API and added **Auto-Prefixing** for landmark actions.

## [1.0.0] - 2026-05-08

### Added
- **Initial Release**: Landmark Manifest Protocol for autonomous agents.
- **Semantic Landmarks**: Logical tool grouping for efficient context discovery.
- **SmartRepair Engine**: Automated agent recovery with actionable remedies.
- **High-Performance Sequencing**: Execution of multi-step tool chains in a single turn.
- **Variable Piping**: Server-side data flow between actions via `$alias.field`.
- **Intelligent Type Mapping**: Automatic conversion of Pydantic models and Python types to protocol schemas.
- **Solaris Gauntlet Benchmark**: Comparative suite for performance and cost validation.

### Changed
- **License**: Project released under the GPLv3 License.

---
*Maintained by Marc Stöcker.*
