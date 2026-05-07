import pytest
from fastapi import FastAPI
from pydantic import BaseModel
from elemm_v2.core.manager import AIProtocolManager
from elemm_v2.core.models import Landmark
from elemm_v2.core.sequencer import PipeResolver

class MockResponse(BaseModel):
    status: str
    data: int

def test_manager_binding_and_enrichment():
    manager = AIProtocolManager(instructions="Test instructions")
    
    @manager.bind("test_action")
    def my_tool(name: str, age: int = 20) -> MockResponse:
        """My tool description."""
        return MockResponse(status="ok", data=age)

    # Prüfe ob Landmark registriert wurde
    assert "test_action" in manager.landmarks
    lm = manager.landmarks["test_action"]
    
    # Prüfe automatische Parameter-Extraktion
    assert len(lm.parameters) == 2
    assert lm.parameters[0].name == "name"
    assert lm.parameters[1].name == "age"
    assert lm.parameters[1].required is False

    # Prüfe Response-Inference
    assert lm.response_schema["type"] == "object"
    assert "status" in lm.response_schema["properties"]

    # Prüfe Description Enrichment
    assert "PIPING: Returns status, data" in lm.description
    assert "My tool description" in lm.description

@pytest.mark.asyncio
async def test_manager_call_action_with_sanitization():
    manager = AIProtocolManager(instructions="Test")
    
    @manager.bind("tool")
    def tool(q: str):
        return {"received": q}

    # Teste Small Model Defense (Halluziniertes Präfix q=)
    res = await manager.call_action("tool", {"q": "q=my_value"})
    assert res["received"] == "my_value"

@pytest.mark.asyncio
async def test_manager_noise_filtering():
    manager = AIProtocolManager(instructions="Test", noise_keys=["internal_id"])
    
    @manager.bind("tool")
    def tool():
        return {"id": 1, "internal_id": "secret", "data": "val"}

    res = await manager.call_action("tool", {})
    assert "id" in res
    assert "data" in res
    assert "internal_id" not in res

def test_pipe_resolver_implicit_index():
    context = {
        "res": [{"id": "A"}, {"id": "B"}]
    }
    # v1 Genius: Sollte automatisch Index 0 nehmen
    val, err = PipeResolver.resolve("$res.id", context)
    assert val == "A"
    assert err is None

def test_manager_welcome_message():
    manager = AIProtocolManager(instructions="Test")
    manager.welcome_message = "Hello Agent"
    
    md = manager.get_manifest_md()
    assert "> Hello Agent" in md

def test_manager_auto_discovery():
    app = FastAPI()
    manager = AIProtocolManager(instructions="Test")

    @app.get("/items/{id}", tags=["store"])
    async def get_item(id: int):
        """Get an item from store."""
        return {"id": id}

    manager.bind_to_app(app)
    
    # Landmark ID sollte "store:get_item" sein (Tag:Name)
    assert "store:get_item" in manager.landmarks
    lm = manager.landmarks["store:get_item"]
    assert "Get an item from store" in lm.description
    assert lm.parameters[0].name == "id"
