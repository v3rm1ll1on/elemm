import pytest
from elemm.core.manager import AIProtocolManager
from elemm.core.sequencer import SequenceEngine

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
    
    results = await engine.run(actions, {})
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
    
    results = await engine.run(actions, {})
    assert results[0]["result"]["status"] == "error"
    # Da call_action Parameter-Validierung macht, bricht es ab bevor der Handler (und die Remedy) erreicht wird.
    assert "missing" in results[0]["result"]["message"].lower()
    assert "required_param" in results[0]["result"]["message"]

def test_pipe_resolver_complex_paths():
    manager = AIProtocolManager()
    engine = SequenceEngine(manager)
    context = {
        "res": [
            {"id": "A", "val": 10},
            {"id": "B", "val": 20}
        ]
    }
    
    # Test Index-Piping $res[1].val
    val, err = engine.resolve_all("$res[1].val", context)
    assert val == 20
    assert err is None
    
    # Test Embedded Piping (Supported in v1.0.0 via interpolation)
    text, err = engine.resolve_all("The value is $res[0].id", context)
    assert text == "The value is A"
    assert err is None

@pytest.mark.asyncio
async def test_sequencer_conditions():
    manager = AIProtocolManager()
    
    @manager.bind("always")
    def always(): return {"status": "ok"}
    
    @manager.bind("conditional")
    def conditional(): return {"executed": True}

    engine = SequenceEngine(manager)
    
    # Test skipping
    actions = [
        {"action": "always", "alias": "a"},
        {"action": "conditional", "condition": "$a.status == 'error'"}
    ]
    results = await engine.run(actions, {})
    assert len(results) == 2
    assert results[1]["result"]["status"] == "skipped"

    # Test executing
    actions = [
        {"action": "always", "alias": "a"},
        {"action": "conditional", "condition": "$a.status == 'ok'"}
    ]
    results = await engine.run(actions, {})
    assert len(results) == 2
    assert results[1]["result"]["executed"] is True
