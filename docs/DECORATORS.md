# Elemm Reference: Decorators & Options

Elemm bietet eine intuitive API, um FastAPI-Routen als AI Landmarks zu markieren. Dabei übernimmt das Framework im Hintergrund die schwere Arbeit der Schema-Extraktion.

---

## Die Decorator-Aliase (DX-Power)

Elemm bietet drei spezialisierte Decorators. Der Hauptunterschied liegt im **vorkonfigurierten Standard-Typ**:

| Decorator | Default `type` | Empfohlene Nutzung |
| :--- | :--- | :--- |
| **`@ai.tool(id=...)`** | `"read"` | Für reine Informationsabfragen (Search, Get, List). |
| **`@ai.action(id=...)`** | `"write"` | Für zustandsverändernde Aktionen (Create, Update, Delete). |
| **`@ai.landmark(id=...)`** | *None* | Generisch. Erfordert manuelle Angabe von `type`. |

```python
# Beispiel für automatische Typisierung:
@ai.tool(id="get_user") # Automatisch type="read"
@ai.action(id="delete_user") # Automatisch type="write"
```

---

## Parameter-Referenz (Deep Dive)

### `id` (string, Required)
Die eindeutige Kennung des Tools. Elemm sanitiert diese automatisch (z.B. werden Sonderzeichen in Unterstriche umgewandelt).

### `type` (string)
Definiert die Natur der Aktion. 
- `read`: Informationsbeschaffung.
- `write`: Datenänderung (wird im Read-Only Modus ausgefiltert).
- `navigation`: Signposts für neue Ebenen.

### `remedy` (string, Optional)
Spezifische Korrekturanweisung bei Validierungsfehlern. Siehe [REPAIR_KIT.md](REPAIR_KIT.md).

### `opens_group` (string, Optional)
Signalisiert der KI, dass dieser Landmark eine neue logische Gruppe öffnet. Wird primär für die automatische Navigation genutzt.

---

## Automatisierte Features (The "Magic")

Elemm extrahiert mehr als nur den Funktionsnamen. Folgende Features sind vollautomatisch aktiv:

### 1. Enum-Support
Wenn du Python `Enum` Typen in deinen Argumenten nutzt, erkennt Elemm diese automatisch und mappt sie auf `options` im Manifest. Die KI sieht exakt, welche Werte erlaubt sind.

### 2. Response Schema Extraction
Elemm inspiziert das `response_model` deiner FastAPI-Route. Die KI erhält eine strukturierte Vorstellung davon, was das Tool zurückgeben wird, was die Reasoning-Qualität enorm steigert.

### 3. Nested Models
Dank Pydantic-Integration werden auch tief geschachtelte Modelle korrekt (flach oder strukturiert) für das Manifest aufbereitet, inklusive Beschreibungen und Constraints (`ge`, `le`, `pattern`).

### 4. Global Access vs. Context
- **`global_access=True`**: Landmark ist in der Root-Ebene UND in jedem Sub-Manifest sichtbar.
- **`hidden=True`**: Landmark ist im Code registriert, aber für die KI unsichtbar (außer über die interne Audit-Gruppe `_INTERNAL_ALL_`).
