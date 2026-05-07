import pytest
from elemm_v2.core.manager import AIProtocolManager
from elemm_v2.core.sequencer import SequenceEngine, PipeResolver

@pytest.mark.asyncio
async def test_sequencer_piping_and_remedy():
    manager = AIProtocolManager(instructions="Test")
    
    @manager.bind("step1")
    def step1():
        return {"token": "RT-123", "meta": {"id": 1}}
    
    @manager.bind("step2")
    def step2(token: str):
        return {"status": "ok", "token_used": token}

    engine = SequenceEngine(manager)
    
    actions = [
        {"action": "step1", "alias": "res1"},
        {"action": "step2", "parameters": {"token": "$res1.token"}}
    ]
    
    results = await engine.run(actions)
    assert len(results) == 2
    assert results[1]["result"]["token_used"] == "RT-123"

@pytest.mark.asyncio
async def test_sequencer_error_enrichment():
    manager = AIProtocolManager(instructions="Test")
    
    @manager.bind("fail_tool")
    def fail_tool(required_param: str):
        return {"status": "error", "message": "Missing something"}

    manager.landmarks["fail_tool"].remedy = "Use 'correct_value' for this param."
    
    engine = SequenceEngine(manager)
    actions = [{"action": "fail_tool", "parameters": {}}]
    
    results = await engine.run(actions)
    assert results[0]["result"]["status"] == "error"
    assert "REMEDY" in results[0]["result"]["remedy"] or "Use 'correct_value'" in results[0]["result"]["remedy"]

def test_pipe_resolver_complex_paths():
    context = {
        "res": [
            {"id": "A", "val": 10},
            {"id": "B", "val": 20}
        ]
    }
    
    # Test Index-Piping $res[1].val
    val, err = PipeResolver.resolve("$res[1].val", context)
    assert val == 20
    assert err is None
    
    # Test Embedded Piping
    text, err = PipeResolver.resolve("The value is $res[0].id", context)
    assert text == "The value is A"
