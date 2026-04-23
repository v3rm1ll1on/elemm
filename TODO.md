# Elemm Roadmap & TODOs

## Architektur & Refactoring
- [ ] **Multi-Framework Support**: `LandmarkBridge` in `mcp.py` framework-agnostisch halten.
- [ ] **Adapter-Pattern**: Weitere Adapter für Frameworks wie Flask, Django oder Litestar erstellen (analog zu `mcp_fastapi.py`).
- [ ] **Discovery Engine**: Die Logik in `discovery.py` weiter verfeinern, um noch mehr Edge-Cases von Pydantic v2 und komplexen FastAPI-Abhängigkeiten abzudecken.

## Features
- [ ] **Auto-Remedy**: KI-gestützte Vorschläge für Korrekturen bei Validierungsfehlern (über das aktuelle statische System hinaus).
- [ ] **Tool-Chaining**: Unterstützung für die Definition von Abhängigkeiten zwischen Landmarks direkt im Code.
- [ ] **Auth-Bridge**: Einheitliches System zur Weitergabe von Auth-Headern zwischen MCP-Clients und den internen API-Routen.

## MCP Integration
- [ ] **Dynamic Tool Listing**: Performance-Optimierung für `list_tools`, wenn die Anzahl der Landmarks sehr groß wird.
- [ ] **Stateful Navigation**: Verbesserte Session-Isolierung für den SSE-Transport.
