import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from elemm.mcp import LandmarkBridge
from elemm.models import AIAction
import mcp.types as types

@pytest.fixture
def mock_manager():
    manager = MagicMock()
    manager.agent_welcome = "Test AI"
    manager.protocol_instructions = "Do test stuff."
    manager.navigation_landmarks = [{"id": "hr", "description": "HR module"}]
    
    # Mock some actions
    action1 = AIAction(id="get_users", type="read", description="List users", groups=["hr"])
    action2 = AIAction(id="reset_system", type="write", description="Reset", groups=["admin"], global_access=False)
    manager.actions = [action1, action2]
    
    # Mock methods
    manager.get_manifest = MagicMock(return_value={"actions": [{"id": "get_users", "parameters": []}]})
    manager.call_action = AsyncMock(return_value={"status": "ok", "remedy": "Try again"})
    
    return manager

@pytest.mark.asyncio
async def test_bridge_strip_namespace():
    bridge = LandmarkBridge(manager=None)
    assert bridge._strip_namespace("my-server-get_manifest") == "get_manifest"
    assert bridge._strip_namespace("unknown-tool") == "unknown-tool"

@pytest.mark.asyncio
async def test_bridge_handle_core_tools(mock_manager):
    bridge = LandmarkBridge(manager=mock_manager)
    
    # Test get_manifest
    res = await bridge._handle_core_dispatch("get_manifest", {})
    assert isinstance(res[0], types.TextContent)
    assert "# ELEMM MANIFEST: Test AI" in res[0].text

    # Test navigate
    res = await bridge._handle_navigate("navigate", {"landmark_id": "hr"})
    assert bridge.ctx == "hr"
    assert "Switched to hr." in res[0].text

@pytest.mark.asyncio
async def test_bridge_auto_pilot(mock_manager):
    bridge = LandmarkBridge(manager=mock_manager)
    bridge.ctx = "root"
    
    action_meta = mock_manager.actions[0] # get_users in group 'hr'
    
    switched = await bridge._handle_auto_pilot(action_meta)
    assert switched is True
    assert bridge.ctx == "hr"

@pytest.mark.asyncio
async def test_bridge_format_result(mock_manager):
    bridge = LandmarkBridge(manager=mock_manager)
    action_meta = mock_manager.actions[0]
    
    res = {"data": 123, "remedy": "Fixed it", "instruction": "Look here"}
    output = bridge._format_action_result("my_tool", res, action_meta, auto_switched=True)
    
    assert "NOTE: Look here" in output
    assert "REMEDY: Fixed it" in output
    assert '{"data":123}' in output.replace(" ", "") # Whitespace insensitive
    assert "(Switched)" in output

@pytest.mark.asyncio
async def test_bridge_error_formatting():
    bridge = LandmarkBridge(manager=None)
    e = Exception("Something went wrong")
    output = bridge._format_error_feedback(e)
    assert "ERR: Something went wrong" in output
    assert "ACTION:" in output
