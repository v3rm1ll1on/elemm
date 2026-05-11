# Elemm Roadmap and Tasks

## Phase 1: Protocol v1.0 Stabilization (Completed)
- [x] Implementation of the Landmark Manifest Protocol discovery handshake.
- [x] High-performance `execute_sequence` with native variable piping.
- [x] SmartRepair engine for autonomous agent recovery.
- [x] Solaris Gauntlet benchmark suite with token and cost analysis.
- [x] Comprehensive documentation and PyPI release.

## Phase 2: Gateway v1.1.0 — Security and Integration (Completed)
- [x] **Elemm Gateway**: Universal MCP server with broker architecture (8 core tools only).
- [x] **OpenAPI Bridge**: Automatic parsing of OpenAPI 3.x / Swagger 2.0 into Elemm landmarks.
- [x] **GraphQL Bridge**: Introspection-based mapping of GraphQL endpoints to landmarks.
- [x] **Security Policy Engine (Guardian)**: Pattern blacklists, landmark restrictions, method filtering.
- [x] **Vault Manager**: Local credential management with apiKey, bearer, and basic auth.
- [x] **Mandatory Handshake Protocol**: Session authorization via `get_manifest()`.
- [x] **Session Isolation**: Parallel task support via `session_id`.
- [x] **Dynamic Token Mapping**: Vault-based authentication injection into tool calls.
- [x] **SSE Transport**: Web-based MCP client support via `--transport sse`.
- [x] **Complete Documentation Overhaul**: 7 docs covering all features.

## Phase 3: Ecosystem and Hardening (Next)
- [ ] **OAuth2 Integration**: Support secure OAuth2 flows for APIs requiring interactive authentication.
- [ ] **Conditional Branching**: `condition` field in `execute_sequence` steps for if/else logic.
- [ ] **Streaming Support**: Implement result streaming for long-running tool sequences.
- [ ] **FastAPI Multi-Tenant Support**: Enable isolated protocol instances for multi-user environments.

## Phase 4: Ecosystem and Tooling (Future)
- [ ] **Elemm Visualizer**: A debugger for visualizing sequences and piped variable resolutions.
- [ ] **Advanced Client SDK**: High-level library for building Elemm-compliant clients.
- [ ] **Landmark Repository**: A library of pre-built landmarks for common enterprise tasks (SQL, Kubernetes, AWS).
- [ ] **TTL-Based Session Persistence**: Optional caching to relax the handshake requirement for stable connections.
