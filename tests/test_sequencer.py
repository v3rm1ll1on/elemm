import pytest
from elemm.core.sequencer import SequenceEngine
from elemm.core.manager import AIProtocolManager

def test_pipe_resolver_full_match():
    manager = AIProtocolManager()
    engine = SequenceEngine(manager)
    context = {"res1": {"id": 123, "data": {"key": "val"}}, "list": [{"name": "item0"}, {"name": "item1"}]}
    
    # Simple field
    val, err = engine.resolve_all("$res1.id", context)
    assert val == 123
    assert err is None
    
    # List access
    val, err = engine.resolve_all("$list[1].name", context)
    assert val == "item1"
    
    # List access - explicit index required if multiple items
    val, err = engine.resolve_all("$list[0].name", context)
    assert val == "item0"
    assert err is None

def test_pipe_resolver_no_substring_support():
    manager = AIProtocolManager()
    engine = SequenceEngine(manager)
    context = {"user": {"name": "Siddy"}}
    # Substring resolution is deprecated in favor of strict parameter piping
    val, err = engine.resolve_all("Hello $user.name!", context)
    assert val == "Hello $user.name!"

@pytest.mark.asyncio
async def test_sequence_engine():
    manager = AIProtocolManager(instructions="...")
    
    @manager.bind("step1")
    def step1(): return {"uid": "user-1"}
    
    @manager.bind("step2")
    def step2(user_id: str): return {"msg": f"Welcome {user_id}"}

    engine = SequenceEngine(manager)
    actions = [
        {"action": "step1", "alias": "s1"},
        {"action": "step2", "parameters": {"user_id": "$s1.uid"}}
    ]
    
    results = await engine.run(actions, {})
    assert len(results) == 2
    assert results[0]["result"]["uid"] == "user-1"
    assert results[1]["result"]["msg"] == "Welcome user-1"
