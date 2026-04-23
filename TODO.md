# Elemm Roadmap & TODOs

## Architektur & Core (v0.9.0 Status: Achieved)
- [x] **Framework-Agnostic Core**: LandmarkBridge ist nun vollständig entkoppelt von FastAPI.
- [x] **Native Auto-Discovery**: Pydantic & Enum Support für reine Python-Module implementiert.
- [x] **Agent Repair Kit (Native)**: ActionError Support für CLI/Stdio Umgebungen.

## Features & Next Steps
- [ ] **AI-Powered Remedies**: Integration von LLM-Calls zur Generierung von dynamischen Korrekturvorschlägen (Auto-Fix).
- [ ] **Landmark Chaining**: Deklarative Definition von Abhängigkeiten zwischen Landmarks direkt im Code.
- [ ] **Auth-Scoping 2.0**: Verbesserte Unterstützung für Multi-Tenant Umgebungen im Gateway.
- [ ] **Plugin System**: Erleichterte Integration von Drittanbieter-Tools (z.B. LangChain Tools) in Landmarks.

## MCP & Client Support
- [ ] **Browser-Based Discovery**: Ein interaktiver Landmark-Explorer für Entwickler.
- [ ] **Stateful SSE**: Noch robustere Session-Isolierung für Cloud-Deployments.
- [ ] **Telemetry**: Opt-in Metriken über Navigationspfade und Tool-Usage für Agenten-Audits.
