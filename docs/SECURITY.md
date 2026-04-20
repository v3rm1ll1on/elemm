# Elemm Security: Shielding & Read-Only 🛡️

Elemm wirkt als Schutzschild, indem es technische Komplexität vor der KI verbirgt und kritische Kanäle überwacht.

---

## 1. Managed Parameters (Auto-Shielding)

Elemm filtert nicht nur Authentifizierungs-Daten, sondern erkennt auch automatisch **interne Felder**, die für eine KI keinerlei Bedeutung haben oder ein Sicherheitsrisiko darstellen könnten.

### Automatisch versteckte Felder:
Folgende Parameter werden zwar im Code verarbeitet, aber **nie** im KI-Manifest angezeigt:
- `request` (FastAPI Request Objekt)
- `response` (FastAPI Response Objekt)
- `session` / `session_id`
- `background_tasks`
- `db` / `database` (sofern als Dependency erkannt)

### `managed_by: protocol`
Wichtig für die KI: Diese Felder werden nicht einfach gelöscht. Im Manifest werden sie als `managed_by: protocol` markiert. Die globalen `protocol_instructions` erklären der KI: *"Diese Felder existieren, aber das System kümmert sich um sie. Du musst sie nicht setzen."* Das verhindert, dass die KI versucht, diese Felder zu raten oder Fehlermeldungen wegen "fehlender Argumente" halluziniert.

---

## 2. Das "Backdoor"-Feature für Audits 🚪

Manchmal müssen Administratoren oder interne Audit-Agenten Zugriff auf Dinge haben, die vor "normalen" KIs versteckt sind (Tools mit `hidden=True`).

Elemm bietet dafür die interne Gruppe **`_INTERNAL_ALL_`**:
- Wenn ein Request das Manifest für die Gruppe `_INTERNAL_ALL_` abfragt, liefert Elemm **alle** Landmark-Tools aus, egal ob sie als `hidden` markiert sind oder nicht.
- **Sicherheitshinweis:** Schütze den Zugriff auf diesen Gruppen-Parameter in deiner Infrastruktur, da er die komplette API-Oberfläche (inklusive Debug-Tools) enthüllt.

---

## 3. Dynamic Read-Only Protection

Der `read_only=true` Modus ist ein harter Filter:
- Er entfernt physisch alle `write` Landmark-Typen und alle Routen mit Methoden außer `GET` oder `HEAD`.
- Dies ist der ultimative Schutz vor "Prompt Injection" Angriffen, die darauf abzielen, Daten zu löschen oder zu verändern.
