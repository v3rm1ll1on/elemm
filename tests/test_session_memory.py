import pytest
from elemm.core.manager import AIProtocolManager
from elemm.core.models import LandmarkRegistry, Landmark

class MockRegistry(LandmarkRegistry):
    def get(self, id):
        return None

@pytest.fixture
def manager():
    return AIProtocolManager(registry=MockRegistry())

@pytest.mark.asyncio
async def test_session_step_counter_increments_on_call_action(manager):
    """Verify that every call_action increments the global step counter."""
    
    @manager.landmark("test:ping")
    def ping():
        return "pong"
    
    # 1. First call
    await manager.call_action("test:ping", {})
    assert manager.session_step_counter == 1
    assert manager.global_context["step0"] == "pong"
    
    # 2. Second call
    await manager.call_action("test:ping", {})
    assert manager.session_step_counter == 2
    assert manager.global_context["step1"] == "pong"

@pytest.mark.asyncio
async def test_session_step_counter_increments_on_execute_sequence(manager):
    """Verify that execute_sequence increments the counter by the number of steps."""
    
    @manager.landmark("test:echo")
    def echo(msg: str):
        return msg
    
    # 1. Run sequence with 2 steps
    await manager.execute_sequence({
        "steps": [
            {"action": "test:echo", "parameters": {"msg": "first"}},
            {"action": "test:echo", "parameters": {"msg": "second"}}
        ]
    })
    
    assert manager.session_step_counter == 2
    assert manager.global_context["step0"] == "first"
    assert manager.global_context["step1"] == "second"
    
    # 2. Run another sequence
    await manager.execute_sequence({
        "steps": [
            {"action": "test:echo", "parameters": {"msg": "third"}}
        ]
    })
    
    assert manager.session_step_counter == 3
    assert manager.global_context["step2"] == "third"
    # Ensure step0/step1 still exist (Persistence)
    assert manager.global_context["step0"] == "first"

@pytest.mark.asyncio
async def test_cross_turn_piping(manager):
    """Verify that we can pipe results from a previous call into a new call."""
    
    @manager.landmark("test:get_id")
    def get_id():
        return {"id": "123"}
        
    @manager.landmark("test:process")
    def process(target_id: str):
        return f"processed {target_id}"
        
    # Turn 1: Get ID
    await manager.call_action("test:get_id", {})
    
    # Turn 2: Process using $step0.id
    res = await manager.call_action("test:process", {"target_id": "$step0.id"})
    assert res == "processed 123"
    assert manager.global_context["step1"] == "processed 123"

@pytest.mark.asyncio
async def test_mixed_piping_sequence(manager):
    """Verify piping between single calls and sequences."""
    
    @manager.landmark("test:math")
    def add(a: int, b: int):
        return a + b
        
    # 1. Single call
    await manager.call_action("test:math", {"a": 10, "b": 5}) # -> $step0 = 15
    
    # 2. Sequence using $step0
    results = await manager.execute_sequence({
        "steps": [
            {"action": "test:math", "parameters": {"a": "$step0", "b": 5}}, # 15 + 5 = 20 ($step1)
            {"action": "test:math", "parameters": {"a": "$step1", "b": 10}} # 20 + 10 = 30 ($step2)
        ]
    })
    
    assert results[0]["result"] == 20
    assert results[1]["result"] == 30
    assert manager.session_step_counter == 3
    assert manager.global_context["step2"] == 30

@pytest.mark.asyncio
async def test_alias_persistence(manager):
    """Verify that aliases stay even as step indices increment."""
    
    @manager.landmark("test:ping")
    def ping():
        return "pong"
        
    await manager.call_action("test:ping", {"_alias": "my_ping"})
    assert manager.global_context["my_ping"] == "pong"
    assert manager.global_context["step0"] == "pong"
    
    await manager.call_action("test:ping", {})
    assert manager.global_context["my_ping"] == "pong" # Still there
    assert manager.session_step_counter == 2
