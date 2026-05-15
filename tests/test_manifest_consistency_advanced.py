# Copyright (C) 2026 Antigravity (DeepMind)
import pytest
import json
from fastapi.testclient import TestClient
from fastapi import FastAPI
from elemm.core.manager import AIProtocolManager
from elemm.core.models import Landmark, Parameter
from elemm.gateways.fastapi import FastAPIGateway

@pytest.fixture
def manager():
    return AIProtocolManager()

@pytest.fixture
def client(manager):
    app = FastAPI()
    gateway = FastAPIGateway(manager)
    gateway.bind_to_app(app)
    return TestClient(app)

def test_json_structure_integrity(client, manager):
    """
    PRÜFUNG 1: Struktur
    Stellt sicher, dass das JSON-Format die korrekten Top-Level-Felder hat.
    """
    manager.landmark("test:action", description="Test")(lambda: "ok")
    
    resp = client.get("/.well-known/elemm-manifest.md?format=json")
    assert resp.status_code == 200
    data = resp.json()
    
    # Root Check
    assert data["version"] == "2.0"
    assert "landmarks" in data
    assert "pagination" in data
    assert data["is_root"] is True
    
    # Pagination Check
    pagination = data["pagination"]
    assert "total" in pagination
    assert "offset" in pagination
    assert "limit" in pagination
    assert "has_more" in pagination

def test_require_params_and_returns_presence(client, manager):
    """
    PRÜFUNG 2: Require Param + Returns
    Stellt sicher, dass Parameter und Rückgabetypen IMMER da sind.
    """
    manager.landmark(
        "it:restart_service", 
        description="Restarts a service",
        parameters=[Parameter(name="service_name", type="string", required=True, description="Name of the service")],
        returns="ServiceStatus"
    )(lambda service_name: {"status": "restarted"})

    # Wir müssen in die Area "it" schauen, um das Tool zu sehen, oder das Tool direkt inspizieren
    resp = client.get("/.well-known/elemm-manifest.md?landmark_id=it:restart_service&format=json")
    data = resp.json()
    
    landmark = data["landmarks"][0]
    assert landmark["id"] == "it:restart_service"
    assert landmark["returns"] == "ServiceStatus"
    assert isinstance(landmark["parameters"], list)
    assert landmark["parameters"][0]["name"] == "service_name"
    assert landmark["parameters"][0]["description"] == "Name of the service"
    assert landmark["parameters"][0]["required"] is True

def test_squishing_and_truncation_logic(client, manager):
    """
    PRÜFUNG 3: Squishing/Truncating
    Stellt sicher, dass wir bei großen Listen korrekt paginieren und kürzen.
    """
    # Erzeuge 10 Test-Landmarks auf ROOT Ebene (ohne Doppelpunkt)
    for i in range(10):
        manager.landmark(f"tool_{i}", description=f"Tool {i}")(lambda: "ok")
        
    # Test Limit
    resp = client.get("/.well-known/elemm-manifest.md?format=json&limit=3")
    data = resp.json()
    # Wir zählen nur die tool_i landmarks, da evtl. andere durch fixtures da sind
    tools = [l for l in data["landmarks"] if l["id"].startswith("tool_")]
    assert len(tools) == 3
    assert data["pagination"]["total"] >= 10
    assert data["pagination"]["has_more"] is True
    
    # Test Offset
    resp = client.get("/.well-known/elemm-manifest.md?format=json&limit=1&offset=1")
    data2 = resp.json()
    tools2 = [l for l in data2["landmarks"] if l["id"].startswith("tool_")]
    assert tools2[0]["id"] == "tool_1"
    assert data2["pagination"]["offset"] == 1

def test_parity_between_sources(client, manager):
    """
    PRÜFUNG 4: Parität (Native vs Bridge)
    Stellt sicher, dass der Output identisch ist, egal woher die Landmark kommt.
    """
    # 1. Native Landmark mit explizitem Namespace
    manager.landmark("native:tool", description="Native Tool", returns="string")(lambda: "ok")
    
    # Direkte Prüfung des Objekts (jetzt mit korrekter ID)
    native_obj = manager.landmarks["native:tool"]
    assert native_obj.returns == "string"

    # 2. Mock eine "External" Landmark (mit gleichem Schema)
    manager.landmarks["external:tool"] = Landmark(
        id="external:tool",
        description="External Tool",
        parameters=[],
        returns="string",
        handler=lambda: "ok"
    )
    
    # Wir fragen das Manifest für beide an
    resp = client.get("/.well-known/elemm-manifest.md?landmark_id=native:tool,external:tool&format=json")
    data = resp.json()
    
    # Suche die Tools in der Liste
    native = next(l for l in data["landmarks"] if l["id"] == "native:tool")
    external = next(l for l in data["landmarks"] if l["id"] == "external:tool")
    
    # Vergleiche Felder
    assert native["returns"] == external["returns"]
    assert native["description"] == "Native Tool"
    assert external["description"] == "External Tool"
    
    # Sicherstellen, dass die Struktur identisch ist
    assert set(native.keys()) == set(external.keys())
    assert isinstance(native["parameters"], list)
    assert isinstance(external["parameters"], list)
