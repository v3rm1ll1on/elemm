import pytest
from fastapi import FastAPI, Header, Depends, Request
from pydantic import BaseModel, Field
from enum import Enum
from elemm import FastAPIProtocolManager

class Color(str, Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"

class Item(BaseModel):
    id: str = Field(..., description="Unique item ID")
    name: str = Field(..., example="Gadget v1")
    color: Color = Color.RED

def get_current_user():
    return "test_user"

@pytest.fixture
def app():
    app = FastAPI(title="Test App")
    ai = FastAPIProtocolManager(agent_welcome="Test Welcome", debug=True)
    
    @app.get("/items/{item_id}")
    @ai.landmark(id="get_item", type="read")
    async def get_item(item_id: str, x_api_key: str = Header(..., description="API Key Header")):
        return {"item_id": item_id}

    @app.post("/items")
    @ai.landmark(id="create_item", type="write", instructions="Verify color before creating.")
    async def create_item(item: Item, request: Request, user: str = Depends(get_current_user)):
        return {"status": "created"}

    @app.get("/secure")
    @ai.landmark(id="secure_action", type="read")
    async def secure_action(authorization: str = Header(None)):
        return {"secure": True}

    ai.bind_to_app(app)
    return ai

def test_discovery_basic(app):
    manifest = app.get_manifest()
    actions = {a.id: a for a in app.actions}
    
    assert "get_item" in actions
    assert "create_item" in actions
    assert "secure_action" in actions

def test_header_detection(app):
    actions = {a.id: a for a in app.actions}
    get_item = actions["get_item"]
    
    # Check Header param
    header_param = next(p for p in get_item.parameters if p.name == "x_api_key")
    assert header_param.required is True
    assert "API Key Header" in header_param.description
    assert header_param.managed_by is None # Normal header

def test_sensitive_header_protection(app):
    actions = {a.id: a for a in app.actions}
    secure_action = actions["secure_action"]
    
    auth_param = next(p for p in secure_action.parameters if p.name == "authorization")
    assert auth_param.managed_by == "protocol" # Secure header recognized!

def test_context_injection(app):
    actions = {a.id: a for a in app.actions}
    create_item = actions["create_item"]
    
    # Request and the dependency on get_current_user should be context deps
    assert "request" in create_item.context_dependencies
    assert "user" in create_item.context_dependencies
    
    # They should NOT be in the regular parameters
    param_names = [p.name for p in (create_item.parameters or [])]
    assert "request" not in param_names
    assert "user" not in param_names

def test_enum_and_pydantic_extraction(app):
    actions = {a.id: a for a in app.actions}
    create_item = actions["create_item"]
    
    # Check payload fields
    payload_fields = {p.name: p for p in create_item.payload}
    
    assert "id" in payload_fields
    assert payload_fields["id"].description == "Unique item ID"
    
    assert "name" in payload_fields
    assert payload_fields["name"].example == "Gadget v1"
    
    assert "color" in payload_fields
    assert payload_fields["color"].options == ["red", "green", "blue"]

def test_mcp_export(app):
    mcp_tools = app.get_mcp_tools()
    tool_names = [t["name"] for t in mcp_tools]
    
    assert "get_item" in tool_names
    assert "create_item" in tool_names
    
    create_tool = next(t for t in mcp_tools if t["name"] == "create_item")
    assert "id" in create_tool["inputSchema"]["properties"]
    assert "color" in create_tool["inputSchema"]["properties"]
    # Internal context deps like 'request' should NOT be in MCP schema
    assert "request" not in create_tool["inputSchema"]["properties"]
    
    # Check if remedy is included in description
    assert "Remedy/Error-Handling" in create_tool["description"]
