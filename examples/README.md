# 🤖 elemm vs. Classic MCP: Ein Vergleich

Stell dir vor, du hast zwei Kisten mit Lego-Steinen und willst, dass ein Roboter daraus ein Haus baut.

---

## 🔴 Die normale Kiste (Classic MCP)
**Wie es ohne elemm läuft:**

Stell dir vor, du hast die Lego-Anleitung verloren. Damit dein Roboter weiß, was er tun soll, musst du ihm für jeden einzelnen Stein einen Zettel schreiben:
*   *"Der rote Stein ist für das Dach."*
*   *"Diesen blauen Stein darfst du nur benutzen, wenn es nicht regnet."*
*   *"Wenn der grüne Stein klemmt, dann drück erst den gelben."*

**Das Problem:** Wenn du einen Stein gegen einen größeren austauschst, musst du sofort zu deinem Roboter laufen und den Zettel umschreiben. Vergisst du das, versucht der Roboter den alten Stein einzubauen und alles bricht zusammen. Du schreibst also alles doppelt: Einmal die Bauanleitung und einmal die Zettel für den Roboter. 

**Zu finden in:** [`./classic_mcp`](./classic_mcp)

---

## 🟢 Die Zauber-Kiste (elemm MCP)
**Wie es mit elemm läuft:**

In dieser Kiste sind **Zauber-Steine**. Du musst dem Roboter gar keine Zettel mehr schreiben. Er fragt einfach jeden Stein: *"Hey Stein, was kannst du?"* – und der Stein antwortet ihm:
*   *"Ich bin ein Dachstein, setz mich oben drauf!"*
*   *"Ich klebe nur, wenn du vorher diesen anderen Stein benutzt."*
*   *"Wenn ich hinfalle, dann heb mich einfach wieder auf."*

**Der Vorteil:** Wenn du einen Stein änderst, weiß der Stein das sofort selbst. Der Roboter fragt ihn einfach neu und weiß Bescheid. Du musst nie wieder Zettel schreiben. Du baust einfach nur – und der Roboter versteht dich von ganz allein.

**Zu finden in:** [`./elemm_mcp`](./elemm_mcp)

---

### Was du in den Beispielen findest:

1.  **api.py**: Die Lego-Steine (Deine API).
2.  **mcp_server.py**: Die Brücke (Damit der Roboter die Steine greifen kann).
3.  **client_demo.py**: Der Roboter (Das LLM), der versucht die Aktionen auszuführen.

**Schau dir die `client_demo.py` an:** Im klassischen Teil siehst du einen riesigen "Zettelhaufen" (System Prompt). Im elemm-Teil ist dieser Zettelhaufen leer – weil die Steine (Tools) selbst sprechen können!
