import pytest
import json
from fastapi import FastAPI
from elemm.core.manager import AIProtocolManager
from elemm.gateways.fastapi import FastAPIGateway
from starlette.testclient import TestClient

def test_agent_navigation_flow():
    """
    Simuliert den Workflow eines Agenten: 
    Discovery -> Drill-Down -> Suche -> Pagination
    """
    manager = AIProtocolManager()
    app = FastAPI()
    gateway = FastAPIGateway(manager)
    gateway.bind_to_app(app)
    client = TestClient(app)

    # 1. Setup: Erstelle eine Hierarchie mit vielen Tools
    # Wir erstellen 50 Tools in "Security" um Pagination zu erzwingen
    for i in range(50):
        manager.landmark(f"Security:Tool_{i}")(lambda: "ok")
    
    # Ein paar andere Areas
    manager.landmark("Finance:Audit")(lambda: "ok")
    manager.landmark("HR:Search")(lambda: "ok")

    # --- SCHRITT 1: Root Discovery ---
    resp = client.get("/.well-known/elemm-manifest.md?format=json")
    data = resp.json()
    root_ids = [l["id"] for l in data["landmarks"]]
    
    # Erwartung: Nur die Haupt-Areas (ohne Doppelpunkt)
    assert "Security" in root_ids
    assert "Finance" in root_ids
    assert "HR" in root_ids
    assert "Security:Tool_0" not in root_ids # Keine Deep-Tools im Root! (Kontexthygiene)

    # --- SCHRITT 2: Drill-Down (Inspect Area) ---
    # Agent sieht "Security" und will wissen was drin ist
    resp = client.get("/.well-known/elemm-manifest.md?landmark_id=Security&format=json&limit=20")
    data = resp.json()
    
    # Erwartung: Wir sehen jetzt die Tools der Security Area
    sec_tools = [l["id"] for l in data["landmarks"]]
    assert "Security:Tool_0" in sec_tools
    assert len(sec_tools) == 20 # Limit muss greifen
    assert data["pagination"]["has_more"] is True
    assert data["pagination"]["total"] == 50

    # --- SCHRITT 3: Pagination (Next Page) ---
    resp = client.get("/.well-known/elemm-manifest.md?landmark_id=Security&format=json&limit=20&offset=20")
    data = resp.json()
    sec_tools_page2 = [l["id"] for l in data["landmarks"]]
    assert "Security:Tool_20" in sec_tools_page2
    assert "Security:Tool_0" not in sec_tools_page2 # Keine Überlappung

    # --- SCHRITT 4: Globale Suche ---
    # Agent sucht nach "Audit"
    resp = client.get("/.well-known/elemm/search?query=Audit&format=json")
    data = resp.json()
    search_results = [l["id"] for l in data["landmarks"]]
    assert "Finance:Audit" in search_results
    assert "Security" not in search_results # Filterung muss sauber sein

    # --- SCHRITT 5: Full Integrity Check ---
    # Stellen wir sicher, dass bei ?full=true wirklich ALLES kommt
    resp = client.get("/.well-known/elemm-manifest.md?format=json&full=true")
    data = resp.json()
    all_ids = [l["id"] for l in data["landmarks"]]
    assert len(all_ids) >= 53 # 50 Security + Finance + HR + Areas
    assert "Security:Tool_49" in all_ids

if __name__ == "__main__":
    pytest.main([__file__])
