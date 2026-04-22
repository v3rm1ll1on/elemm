import pytest
from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Optional, List
from elemm import Elemm

# 1. Deep Nesting
class Level3(BaseModel):
    leaf: str = "end"

class Level2(BaseModel):
    next_level: Level3

class Level1(BaseModel):
    branch: Level2

# 2. Circular References (Self-referencing model)
class Category(BaseModel):
    name: str
    parent: Optional['Category'] = None

# Re-evaluate forward refs for Circular Reference (Pydantic v2)
Category.model_rebuild()

def test_deep_nesting_extraction():
    app = FastAPI()
    ai = Elemm(agent_welcome="W")
    
    @app.post("/deep")
    @ai.tool(id="deep_tool")
    def deep_op(item: Level1): return {}
    
    ai.bind_to_app(app)
    manifest = ai.get_manifest()
    
    # Check if the response schema or payload extraction handles deep nesting correctly
    # Currently _extract_response_schema is relatively flat, let's see how it behaves
    action = ai.actions[0]
    assert action.id == "deep_tool"
    # Even if flat, it should at least not crash and return the top-level type
    payload_fields = {p.name: p for p in action.payload}
    assert "branch" in payload_fields

def test_circular_reference_safety():
    app = FastAPI()
    ai = Elemm(agent_welcome="W")
    
    @app.post("/circular")
    @ai.tool(id="circle")
    def circle_op(cat: Category): return {}
    
    # This must NOT cause infinite recursion in Elemm
    ai.bind_to_app(app)
    manifest = ai.get_manifest()
    
    assert ai.actions[0].id == "circle"
    # Pydantic's model_json_schema() handles circularity via $ref, 
    # our simple extractor should just pick up the properties.
    payload_fields = {p.name: p for p in ai.actions[0].payload}
    assert "name" in payload_fields
    assert "parent" in payload_fields

def test_special_character_ids():
    app = FastAPI(openapi_tags=[
        {"name": "User & Admin (Beta)", "description": "Complex Tag"}
    ])
    ai = Elemm(agent_welcome="W")
    
    @app.get("/special", tags=["User & Admin (Beta)"])
    @ai.tool(id="special_tool")
    def special(): return {}
    
    ai.bind_to_app(app)
    manifest = ai.get_manifest()
    
    # The tag "User & Admin (Beta)" should be sanitized to "explore_user_and_admin_beta"
    nav_ids = [n["id"] for n in manifest["navigation"]]
    action_ids = [a["id"] for a in manifest["actions"]]
    assert "explore_user_and_admin_beta" in nav_ids
    assert "explore_user_and_admin_beta" not in action_ids
    assert "explore_user_&_admin_(beta)" not in nav_ids
