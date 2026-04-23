import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from elemm import Elemm
from elemm.core.models import AIAction

def test_duplicate_id_protection():
    manager = Elemm(agent_welcome="Welcome")
    
    # Register first time
    manager.register_action(id="test_id", type="test", description="First")
    assert len(manager.actions) == 2 # test_id + enter_module
    
    # Register second time with same ID
    manager.register_action(id="test_id", type="test", description="Second")
    
    # Still 2 actions, but description updated
    assert len(manager.actions) == 2
    assert any(a.id == "test_id" and a.description == "Second" for a in manager.actions)
    assert "test_id" in manager._registered_ids

def test_prefix_aware_urls():
    # Simulate a proxy mounting the app under /api/v1
    app = FastAPI(root_path="/api/v1", openapi_tags=[{"name": "Orders"}])
    ai = Elemm(agent_welcome="Welcome", openapi_url="/openapi.json")
    
    @app.get("/items")
    @ai.tool(id="get_items", type="read")
    def get_items(): return []
    
    ai.bind_to_app(app)
    
    # Check if openapi_url was prefixed
    assert ai.openapi_url == "/api/v1/openapi.json"
    
    # Check if navigation tool URL was prefixed
    manifest = ai.get_manifest(agent_view=False)
    nav_ids = [n["id"] for n in manifest["navigation"]]
    action_ids = [a["id"] for a in manifest["actions"]]
    
    assert "explore_orders" in nav_ids
    assert "explore_orders" not in action_ids
    
    nav_action = next(n for n in manifest["navigation"] if n["id"] == "explore_orders")
    assert nav_action["url"].startswith("/api/v1/.well-known/elemm/discovery")

def test_discovery_error_handling():
    app = FastAPI()
    ai = Elemm(agent_welcome="Welcome", debug=True)
    
    # A perfectly fine route
    @app.get("/fine")
    @ai.tool(id="fine_tool", type="read")
    def fine(): return {}
    
    # Mock a failing registration
    original_register = ai._register_from_route
    def broken_register(route, meta):
        if "broken" in route.path:
            raise ValueError("Discovery failed")
        return original_register(route, meta)
    
    ai._register_from_route = broken_register
    
    @app.get("/broken")
    @ai.tool(id="broken_tool", type="read")
    def broken(): return {}
    
    # This should not raise!
    ai.bind_to_app(app)
    
    # 'fine_tool' should be there with URL, 'broken_tool' should have NO URL
    fine_action = next(a for a in ai.actions if a.id == "fine_tool")
    broken_action = next(a for a in ai.actions if a.id == "broken_tool")
    
    assert fine_action.url is not None
    assert broken_action.url is None

def test_well_known_error_handling():
    app = FastAPI()
    ai = Elemm(agent_welcome="Welcome")
    app.include_router(ai.get_router())
    
    client = TestClient(app)
    
    # Force an error in manifest generation
    def failing_manifest(*args, **kwargs):
        raise RuntimeError("Something went wrong internally")
    
    ai.get_manifest = failing_manifest # This won't work easily because get_md_manifest calls ManifestGenerator
    # But wait, ai.get_manifest is still used in base.py.
    # Actually, the test should mock the generator if it wants to trigger the catch block.
    
    # Alternatively, just mock ManifestGenerator.generate_markdown
    from unittest.mock import patch
    with patch("elemm.mcp.manifest.ManifestGenerator.generate_markdown", side_effect=RuntimeError("Something went wrong internally")):
        response = client.get("/.well-known/elemm-manifest.md")
        
        assert response.status_code == 200
        text = response.text
        assert "ELEMM PROTOCOL ERROR" in text
        assert "Something went wrong internally" in text
        assert "Remedy" in text
