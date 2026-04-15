import pytest
from fastapi import FastAPI
from elemm.fastapi import FastAPIProtocolManager

def test_auto_navigation_generation():
    tags_metadata = [
        {"name": "SecretModule", "description": "Highly classified tools."}
    ]
    app = FastAPI(openapi_tags=tags_metadata)
    ai = FastAPIProtocolManager(agent_welcome="Welcome")
    
    @ai.landmark(id="classified_tool", type="read", tags=["SecretModule"])
    @app.get("/secret")
    def secret(): return {}

    @ai.landmark(id="global_tool", type="read")
    @app.get("/global")
    def glb(): return {}

    ai.bind_to_app(app)

    # 1. Check Root Manifest (No group)
    manifest = ai.get_manifest(agent_view=False)
    action_ids = [a["id"] for a in manifest["actions"]]
    
    # Should contain global_tool and the AUTO-GENERATED navigation tool
    assert "global_tool" in action_ids
    assert "explore_secretmodule" in action_ids
    assert "classified_tool" not in action_ids # Hidden in root!

    # 2. Check Navigation Tool Details
    nav_tool = next(a for a in manifest["actions"] if a["id"] == "explore_secretmodule")
    assert nav_tool["type"] == "navigation"
    assert nav_tool["opens_group"] == "SecretModule"
    assert "SecretModule" in nav_tool["url"]

    # 3. Check Sub-Manifest (SecretModule)
    manifest = ai.get_manifest(group="SecretModule")
    action_ids = [a["id"] for a in manifest["actions"]]
    
    assert "classified_tool" in action_ids
    assert "global_tool" not in action_ids # Only group members allowed
    assert "explore_secretmodule" not in action_ids 

def test_manual_grouping():
    app = FastAPI()
    ai = FastAPIProtocolManager(agent_welcome="Welcome")
    
    @ai.landmark(id="manual_tool", type="write", groups=["CustomGroup"])
    @app.get("/manual")
    def manual(): return {}

    ai.bind_to_app(app)

    # Root should be empty (except maybe help)
    manifest = ai.get_manifest()
    assert not any(a["id"] == "manual_tool" for a in manifest["actions"])

    # Group filter should work
    manifest = ai.get_manifest(group="CustomGroup")
    assert any(a["id"] == "manual_tool" for a in manifest["actions"])
