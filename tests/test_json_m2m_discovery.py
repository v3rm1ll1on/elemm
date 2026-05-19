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
    
    # 1. Setup Hierarchical Mocks
    # Root Area
    root_area = Landmark(id="city", description="City Root")
    
    # Sub Area
    sub_area = Landmark(id="city:energy", description="Energy Sector")
    
    # Tools under sub area
    tools = []
    for i in range(10):
        t = Landmark(
            id=f"city:energy:tool_{i}",
            description=f"Tool {i}",
            parameters=[Parameter(name="val", description="test", required=True)],
            handler=lambda x: f"ok {x}"
        )
        tools.append(t)
    
    sub_area.tools = tools
    root_area.tools = [sub_area]
    
    # Register in manager
    manager.landmarks["city"] = root_area
    manager.landmarks["city:energy"] = sub_area
    for t in tools:
        manager.landmarks[t.id] = t
        
    gateway = FastAPIGateway(manager)
    gateway.bind_to_app(app)
    return TestClient(app)

def test_json_root_discovery(client):
    """Test standard root discovery in JSON format."""
    resp = client.get("/.well-known/elemm-manifest.md?format=json")
    assert resp.status_code == 200
    data = resp.json()
    
    assert data["version"] == "2.0"
    assert data["is_root"] is True
    assert len(data["landmarks"]) == 1
    assert data["landmarks"][0]["id"] == "city"
    assert data["landmarks"][0]["is_truncated"] is True
    assert data["pagination"]["total"] == 1

def test_json_explore_mode(client):
    """Test that requesting a single area returns its children in JSON."""
    resp = client.get("/.well-known/elemm-manifest.md?format=json&landmark_id=city")
    assert resp.status_code == 200
    data = resp.json()
    
    assert data["parent_id"] == "city"
    # Should show the child: city:energy
    assert len(data["landmarks"]) == 1
    assert data["landmarks"][0]["id"] == "city:energy"
    assert data["landmarks"][0]["is_tool"] is False

def test_json_explore_deep(client):
    """Test drilling down into a sub-category."""
    resp = client.get("/.well-known/elemm-manifest.md?format=json&landmark_id=city:energy")
    assert resp.status_code == 200
    data = resp.json()
    
    assert data["parent_id"] == "city:energy"
    assert data["pagination"]["total"] == 10
    assert len(data["landmarks"]) == 10
    assert data["landmarks"][0]["is_tool"] is True
    assert len(data["landmarks"][0]["parameters"]) == 1

def test_json_pagination_in_explore(client):
    """Verify offset/limit works during exploration."""
    # Request children of city:energy, but only page 2
    resp = client.get("/.well-known/elemm-manifest.md?format=json&landmark_id=city:energy&limit=3&offset=3")
    assert resp.status_code == 200
    data = resp.json()
    
    assert data["pagination"]["offset"] == 3
    assert data["pagination"]["limit"] == 3
    assert len(data["landmarks"]) == 3
    assert data["landmarks"][0]["id"] == "city:energy:tool_3"
    assert data["pagination"]["has_more"] is True

def test_json_tool_direct_inspect(client):
    """If a tool is requested directly, don't enter explore mode, just show the tool."""
    resp = client.get("/.well-known/elemm-manifest.md?format=json&landmark_id=city:energy:tool_5")
    assert resp.status_code == 200
    data = resp.json()
    
    # Should NOT be in explore mode because it's a tool (has handler)
    assert data.get("parent_id") is None
    assert len(data["landmarks"]) == 1
    assert data["landmarks"][0]["id"] == "city:energy:tool_5"

def test_json_search_format(client):
    """Ensure search endpoint also respects format=json with the new structure."""
    resp = client.get("/.well-known/elemm/search?query=energy&format=json")
    assert resp.status_code == 200
    data = resp.json()
    
    assert "landmarks" in data
    assert "pagination" in data
    # Should find city:energy and its tools
    assert any(l["id"] == "city:energy" for l in data["landmarks"])

def test_case_insensitivity_json(client):
    """Test that lowercase IDs in JSON requests work."""
    resp = client.get("/.well-known/elemm-manifest.md?format=json&landmark_id=CITY:ENERGY")
    assert resp.status_code == 200
    data = resp.json()
    assert data["parent_id"] == "city:energy" # Correctly resolved

def test_empty_results_json(client):
    """Test behavior when no landmarks match."""
    resp = client.get("/.well-known/elemm-manifest.md?format=json&landmark_id=nonexistent")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["landmarks"]) == 0
    assert data["pagination"]["total"] == 0
