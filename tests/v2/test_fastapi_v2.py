import pytest
from fastapi import FastAPI, Query
from fastapi.testclient import TestClient
from elemm_v2.core.manager import AIProtocolManager
from elemm_v2.gateways.fastapi import FastAPIGateway

def test_fastapi_repair_handler():
    app = FastAPI()
    manager = AIProtocolManager(instructions="Test")
    
    @app.get("/tool")
    @manager.bind("my_tool")
    def my_tool(param: str = Query(...)):
        return {"ok": True}
    
    gateway = FastAPIGateway(manager)
    gateway.bind_to_app(app)
    
    client = TestClient(app)
    
    # Aufruf ohne erforderlichen Parameter -> Sollte 422 Repair auslösen
    resp = client.get("/tool")
    assert resp.status_code == 422
    data = resp.json()
    assert data["status"] == "error"
    assert "remedy" in data
    assert "inspect_landmark" in data["remedy"]

def test_fastapi_well_known():
    app = FastAPI()
    manager = AIProtocolManager(instructions="Global Instructions")
    gateway = FastAPIGateway(manager)
    gateway.bind_to_app(app)
    
    client = TestClient(app)
    resp = client.get("/.well-known/elemm")
    assert resp.status_code == 200
    assert "ELEMM SYSTEM DIRECTORY" in resp.text
    assert "Global Instructions" not in resp.text # Weil manifest nur Index zeigt
