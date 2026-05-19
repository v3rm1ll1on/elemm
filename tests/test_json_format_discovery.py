# Copyright (C) 2026 Antigravity (DeepMind)
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from elemm.core.manager import AIProtocolManager
from elemm.core.models import Landmark, Parameter
from elemm.gateways.fastapi import FastAPIGateway
import json

@pytest.fixture
def client():
    app = FastAPI()
    manager = AIProtocolManager()
    # Mock data with parameters (Root level, no colon)
    manager.landmarks["energy"] = Landmark(
        id="energy", 
        description="Power sector",
        parameters=[Parameter(name="grid_id", type="string", required=True, description="Target grid ID")],
        handler=lambda: "ok"
    )
    gateway = FastAPIGateway(manager)
    gateway.bind_to_app(app)
    return TestClient(app)

def test_json_manifest_format(client):
    """Verify that format=json returns a proper JSON array."""
    resp = client.get("/.well-known/elemm-manifest.md?format=json")
    print(f"DEBUG Manifest Response: '{resp.text}'")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/json"
    
    data = resp.json()
    assert isinstance(data, dict)
    assert "landmarks" in data
    landmarks = data["landmarks"]
    assert isinstance(landmarks, list)
    assert len(landmarks) >= 1
    
    item = landmarks[0]
    assert item["id"] == "energy"
    assert item["description"] == "Power sector"
    assert len(item["parameters"]) == 1
    assert item["parameters"][0]["name"] == "grid_id"

def test_json_search_format(client):
    """Verify that search with format=json returns proper JSON."""
    resp = client.get("/.well-known/elemm/search?query=energy&format=json")
    
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/json"
    
    data = resp.json()
    assert isinstance(data, dict)
    assert "landmarks" in data
    assert isinstance(data["landmarks"], list)
    assert any(d["id"] == "energy" for d in data["landmarks"])

def test_markdown_is_still_default(client):
    """Ensure that not passing format still returns markdown."""
    resp = client.get("/.well-known/elemm-manifest.md")
    assert resp.status_code == 200
    assert "text/markdown" in resp.headers["content-type"]
    assert "### LANDMARK TOPOLOGY" in resp.text
