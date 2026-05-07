import pytest
from elemm_v2.core.sequencer import PipeResolver, SequenceEngine
from elemm_v2.core.manager import AIProtocolManager

def test_pipe_resolver_full_match():
    context = {"res1": {"id": 123, "data": {"key": "val"}}, "list": [{"name": "item0"}, {"name": "item1"}]}
    
    # Simple field
    val, err = PipeResolver.resolve("$res1.id", context)
    assert val == 123
    assert err is None
    
    # Nested field (if it was implemented, but current pattern is shallow)
    # Actually, current pattern is alias.field. 
    # For nested we'd need more logic. Let's stay with shallow for now.
    
    # List access
    val, err = PipeResolver.resolve("$list[1].name", context)
    assert val == "item1"
    
    # List default (index 0)
    val, err = PipeResolver.resolve("$list.name", context)
    assert val == "item0"

def test_pipe_resolver_substring():
    context = {"user": {"name": "Siddy"}}
    val, err = PipeResolver.resolve("Hello $user.name!", context)
    assert val == "Hello Siddy!"
    assert err is None

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
    
    results = await engine.run(actions)
    assert len(results) == 2
    assert results[0]["result"]["uid"] == "user-1"
    assert results[1]["result"]["msg"] == "Welcome user-1"
