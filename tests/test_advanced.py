import pytest
from fastapi import FastAPI, Query, Header, Depends
from typing import Optional, Union, List
from enum import Enum
from pydantic import BaseModel
from elemm import Elemm
from elemm.core.models import ActionParam
from elemm.core.exceptions import LandmarkNotFoundError

class Status(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"

class NestedModel(BaseModel):
    key: str
    value: int

class ComplexItem(BaseModel):
    status: Status
    tags: List[str]
    metadata: Optional[NestedModel] = None

def test_global_access_and_filtering():
    manager = Elemm(agent_welcome="Welcome")
    
    # 1. Global Tool
    manager.register_action(id="global_tool", type="read", description="G", global_access=True, groups=["GroupA"])
    # 2. Group Tool (Hidden)
    manager.register_action(id="hidden_tool", type="write", description="H", hidden=True, groups=["GroupA"])
    # 3. Normal Group Tool
    manager.register_action(id="normal_tool", type="read", description="N", groups=["GroupA"])

    # Root view (agent_view=True)
    root_manifest = manager.get_manifest(agent_view=True)
    root_ids = [a["id"] for a in root_manifest["actions"]]
    assert "global_tool" in root_ids
    assert "hidden_tool" not in root_ids
    assert "normal_tool" not in root_ids # Not global, not in root

    # GroupA view (agent_view=True)
    group_manifest = manager.get_manifest(group="GroupA", agent_view=True)
    group_ids = [a["id"] for a in group_manifest["actions"]]
    assert "global_tool" in group_ids
    assert "normal_tool" in group_ids
    assert "hidden_tool" not in group_ids # Hidden!

    # 4. Internal All View (unauthorized)
    with pytest.raises(LandmarkNotFoundError, match="Internal access is not configured"):
        manager.get_manifest(group="_INTERNAL_ALL_", agent_view=False)

    # Configure key
    manager.internal_access_key = "secret123"

    # Internal All View (wrong key)
    with pytest.raises(LandmarkNotFoundError, match="Invalid internal access key"):
        manager.get_manifest(group="_INTERNAL_ALL_", agent_view=False, internal_key="wrong")

    # Internal All View (correct key)
    all_manifest = manager.get_manifest(group="_INTERNAL_ALL_", agent_view=False, internal_key="secret123")
    all_ids = [a["id"] for a in all_manifest["actions"]]
    assert "hidden_tool" in all_ids
    # 3 registered + 1 enter_module
    assert len(all_ids) == 3 # enter_module is in navigation
    assert "enter_module" in [n["id"] for n in all_manifest["navigation"]]

def test_complex_type_detection():
    app = FastAPI()
    ai = Elemm(agent_welcome="Welcome")
    
    @app.post("/complex")
    @ai.tool(id="complex_op", type="write")
    def complex_op(
        item: ComplexItem, 
        q: Optional[int] = Query(None, description="Optional query"),
        s: Status = Query(Status.ACTIVE),
        x_custom: str = Header("default", description="Custom Header")
    ):
        return {}

    ai.bind_to_app(app)
    action = ai.actions[0]

    # Check Query Params
    q_param = next(p for p in action.parameters if p.name == "q")
    assert q_param.type == "integer"
    assert q_param.required is False

    s_param = next(p for p in action.parameters if p.name == "s")
    assert s_param.type == "string"
    assert s_param.options == ["active", "inactive"]

    # Check Headers
    h_param = next(p for p in action.parameters if p.name == "x_custom")
    assert h_param.description == "Custom Header"
    assert h_param.default == "default"

    # Check Payload
    payload_map = {p.name: p for p in action.payload}
    assert payload_map["status"].options == ["active", "inactive"]
    assert payload_map["tags"].type == "array"

def test_absolute_vs_relative_openapi_url():
    # Relative should be prefixed
    app_rel = FastAPI(root_path="/v1")
    ai_rel = Elemm(agent_welcome="W", openapi_url="/specs.json")
    ai_rel.bind_to_app(app_rel)
    assert ai_rel.openapi_url == "/v1/specs.json"

    # Absolute should be UNTOUCHED
    app_abs = FastAPI(root_path="/v1")
    ai_abs = Elemm(agent_welcome="W", openapi_url="https://external.com/specs.json")
    ai_abs.bind_to_app(app_abs)
    assert ai_abs.openapi_url == "https://external.com/specs.json"

def test_mcp_legacy_and_list_payload():
    manager = Elemm(agent_welcome="Welcome")
    
    # 1. Legacy Dict Payload
    manager.register_action(
        id="legacy", type="read", description="D", 
        payload={"field1": "string [required]", "field2": "integer"}
    )
    
    # 2. Modern List[ActionParam] Payload
    manager.register_action(
        id="modern", type="write", description="M",
        payload=[ActionParam(name="f3", type="boolean", required=True, description="Desc")]
    )

    from elemm.mcp.bridge import LandmarkBridge
    bridge = LandmarkBridge(manager=manager)
    mcp_tools = bridge.get_full_mcp_definitions()
    
    legacy_tool = next(t for t in mcp_tools if t["name"] == "legacy")
    assert legacy_tool["inputSchema"]["properties"]["field1"]["type"] == "string"
    assert "field1" in legacy_tool["inputSchema"]["required"]

    modern_tool = next(t for t in mcp_tools if t["name"] == "modern")
    assert modern_tool["inputSchema"]["properties"]["f3"]["type"] == "boolean"
    assert "f3" in modern_tool["inputSchema"]["required"]

def test_agent_view_noise_reduction():
    manager = Elemm(agent_welcome="Welcome")
    manager.register_action(
        id="noisy", type="read", description="D",
        method="GET", url="/noisy",
        groups=["A"], global_access=True, required_auth="bearer",
        tags=["T1"], hidden=False
    )
    
    clean_manifest = manager.get_manifest(agent_view=True)
    # Find the noisy action (not the enter_module)
    clean_action = next(a for a in clean_manifest["actions"] if a["id"] == "noisy")
    
    # These fields SHOULD be gone in agent_view
    forbidden = ["groups", "global_access", "required_auth", "tags", "hidden"]
    for field in forbidden:
        assert field not in clean_action
    
    # These should stay
    assert "id" in clean_action
    assert "description" in clean_action
    assert "method" in clean_action

def test_read_only_filtering():
    manager = Elemm(agent_welcome="Welcome")
    
    # 1. Read Action
    manager.register_action(id="read_op", type="read", method="GET", description="R")
    # 2. Write Action (explicit type)
    manager.register_action(id="write_op", type="write", method="POST", description="W")
    # 3. Write Action (inferred from method)
    manager.register_action(id="delete_op", type="read", method="DELETE", description="D")

    # Normal View (read_only=False)
    normal_manifest = manager.get_manifest(read_only=False)
    normal_ids = [a["id"] for a in normal_manifest["actions"]]
    assert len(normal_ids) == 3 # enter_module is in navigation
    assert "enter_module" in [n["id"] for n in normal_manifest["navigation"]]

    # Read-Only View (read_only=True)
    ro_manifest = manager.get_manifest(read_only=True)
    ro_ids = [a["id"] for a in ro_manifest["actions"]]
    assert "read_op" in ro_ids
    assert "write_op" not in ro_ids
    assert "delete_op" not in ro_ids 
    assert len(ro_ids) == 1 # enter_module is in navigation
    assert "enter_module" in [n["id"] for n in ro_manifest["navigation"]]

def test_decorator_aliases():
    app = FastAPI()
    ai = Elemm(agent_welcome="Welcome")
    
    @app.get("/tool")
    @ai.tool(id="tool_alias", type="read", description="T")
    def tool_route(): return {}

    @app.get("/action")
    @ai.action(id="action_alias", type="write", description="A")
    def action_route(): return {}

    ai.bind_to_app(app)
    
    action_ids = [a.id for a in ai.actions]
    assert "tool_alias" in action_ids
    assert "action_alias" in action_ids
