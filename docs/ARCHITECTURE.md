# Elemm Architecture: Hierarchical Navigation

Elemm verwandelt eine flache API in eine strukturierte Welt aus Landmarks.

---

## Automatisierte Navigation (The "Signposts")

Ein Kernfeature von Elemm ist, dass Entwickler **keine manuellen Navigations-Tools** für ihre Gruppen schreiben müssen. 

### Wie es funktioniert:
Elemm inspiziert die `openapi_tags` deines FastAPI-Objekts. Wenn eine Route einen Tag besitzt, der in `openapi_tags` definiert ist, generiert Elemm automatisch einen **Navigation Landmark** (Signpost) für diese Gruppe.

- **Automatisches ID-Prefix**: Jede Gruppe erhält eine ID nach dem Schema `explore_{tag_id}`.
- **Auto-Sanitization**: Ein Tag wie `User & Admin (Beta)` wird automatisch zu `explore_user_and_admin_beta`.
- **Beschreibung**: Die Beschreibung aus `openapi_tags` wird als primäre Instruktion für die Navigation genutzt.

**Das bedeutet:** Setze einfach deine Tags in FastAPI, und Elemm baut dir die komplette Navigations-Hierarchie von selbst.

---

## Token Hygiene & Best Practices

Die hierarchische Struktur spart massiv Token, da nur relevante Tools geladen werden. Aber Vorsicht bei der Nutzung von `global_access=True`:

> [!WARNING]
> **Die "Global-Access" Falle**: Tools mit `global_access=True` tauchen in JEDEM Sub-Manifest auf. Wenn du zu viele globale Tools hast, verlierst du den Vorteil der Token-Ersparnis und riskierst wieder Context-Noise.
> 
> **Best Practice:** Nutze `global_access` nur für absolut essentielle Werkzeuge wie `global_search`, `help` oder `system_status`. Alles andere sollte in thematischen Modulen (Tags) bleiben.

---

## Discovery Lifecycle
1.  **Boot Phase**: `bind_to_app` erkennt Signposts aus Tags.
2.  **Root View**: Agent sieht nur Signposts + Global Tools.
3.  **Module View**: Agent "betritt" Gruppe via `explore_...` und erhält fokussierte Tools.
4.  **Token Savings**: In der Regel wird der Context um den Faktor 10 reduziert.
