import pytest
from typing import Literal, Optional
from enum import Enum
from elemm_v2.core.manager import AIProtocolManager
from elemm_v2.core.context import landmark_ctx

class Color(Enum):
    RED = "red"
    BLUE = "blue"

def test_manager_binding_and_inference():
    manager = AIProtocolManager(instructions="Test instructions")
    
    @manager.bind("test_action")
    def my_handler(name: str, color: Color, mode: Literal["fast", "slow"] = "fast"):
        return {"msg": f"Hello {name}", "secret": "shhh", "color": color.value}

    assert "test_action" in manager.landmarks
    action = manager.landmarks["test_action"]
    
    # Check parameters
    params = {p.name: p for p in action.parameters}
    assert params["name"].type == "string"
    assert params["color"].type == "string"
    assert params["color"].options == ["red", "blue"]
    assert params["mode"].options == ["fast", "slow"]

@pytest.mark.asyncio
async def test_execution_and_noise_filter():
    manager = AIProtocolManager(instructions="...", noise_keys=["secret"])
    
    @manager.bind("test_action")
    async def my_handler(name: str):
        return {"msg": f"Hello {name}", "secret": "12345"}

    res = await manager.call_action("test_action", {"name": "Siddy"})
    assert res["msg"] == "Hello Siddy"
    assert "secret" not in res # Noise filtered!

@pytest.mark.asyncio
async def test_landmark_context():
    manager = AIProtocolManager(instructions="...")
    
    @manager.bind("ctx_tool")
    async def ctx_tool():
        return {"current": landmark_ctx.get()}

    res = await manager.call_action("ctx_tool", {})
    assert res["current"] == "ctx_tool"
    assert landmark_ctx.get() == "root" # Reset after call
