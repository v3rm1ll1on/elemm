import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from elemm.mcp.bridge import LandmarkBridge
from elemm.core.models import AIAction
import mcp.types as types
import json

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
    manager.get_action = MagicMock(side_effect=lambda aid: next((a for a in manager.actions if a.id == aid), None))
    manager.call_action = AsyncMock(return_value=({"status": "ok", "remedy": "Try again"}, 200))
    
    return manager

@pytest.mark.asyncio
async def test_bridge_handle_core_tools(mock_manager):
    bridge = LandmarkBridge(manager=mock_manager)
    
    # Get handle_call_tool from the server
    # We need to find it because it's registered as a decorator
    # The mcp.server.Server stores it in an internal list
    # For testing, we can just call it if we can find where it's stored, 
    # but it's easier to just mock the server or call the bridge's internal methods if they were accessible.
    
    # Actually, LandmarkBridge registers them in _setup_server.
    # We can't easily get the local function back.
    # So let's test _execute_single and _format_result which are public-ish.
    
    # Test _format_result
    res_text = json.dumps({"status": "error", "remedy": "Fixed it"})
    formatted = bridge._format_result("get_users", res_text)
    assert "FAILED. Fixed it" in formatted

    # Test _execute_single
    res = await bridge._execute_single("get_users", {"param": "val"})
    assert "ok" in res

@pytest.mark.asyncio
async def test_bridge_piping_resolution(mock_manager):
    bridge = LandmarkBridge(manager=mock_manager)
    
    local_results = {
        "0": {"token": "RT-1234", "status": "ok"},
        "logs": [{"id": "L1"}, {"id": "L2"}]
    }
    
    # Test simple pipe
    resolved, err = bridge._resolve_params({"id": "$0.token"}, local_results)
    assert resolved["id"] == "RT-1234"
    assert err is None
    
    # Test list pipe
    resolved, err = bridge._resolve_params({"log_id": "$logs[1].id"}, local_results)
    assert resolved["log_id"] == "L2"
    assert err is None
    
    # Test missing alias
    resolved, err = bridge._resolve_params({"id": "$missing.token"}, local_results)
    assert "not found" in err

@pytest.mark.asyncio
async def test_bridge_sequence_execution(mock_manager):
    bridge = LandmarkBridge(manager=mock_manager)
    
    actions = [
        {"action": "get_users", "alias": "users"},
        {"action": "reset_system", "parameters": {"user": "$users.status"}}
    ]
    
    contents = await bridge._handle_execute_sequence(actions)
    assert len(contents) == 1
    assert 'Step 0 (users) (get_users): {"status": "ok", "remedy": "Try again"}' in contents[0].text
    assert 'Step 1 (reset_system): {"status": "ok", "remedy": "Try again"}' in contents[0].text
