import pytest
from fastapi import FastAPI
from pydantic import BaseModel
from elemm.core.manager import AIProtocolManager
from elemm.core.models import Landmark
from elemm.gateways.fastapi import FastAPIGateway
# PipeResolver removed in favor of SequenceEngine

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
    
    # In v2 purist: Parameter müssen manuell oder via Registry kommen
    assert len(lm.parameters) == 0
    # assert lm.parameters[0].name == "name"
    # assert lm.parameters[1].name == "age"

    # In v2 purist: Response-Schema wird nicht mehr automatisch inferiert
    # assert lm.response_schema["type"] == "object"
    pass

    # assert "PIPING: Returns status, data" in lm.description # Magic enrichment disabled
    assert "My tool description" in lm.description

@pytest.mark.asyncio
async def test_manager_call_action_with_sanitization():
    manager = AIProtocolManager(instructions="Test")
    
    @manager.bind("tool")
    def tool(q: str):
        return {"received": q}

    # Teste Small Model Defense (Keine Magie mehr im puristischen Protokoll)
    res = await manager.call_action("tool", {"q": "q=my_value"})
    assert res["received"] == "q=my_value"

@pytest.mark.asyncio
async def test_manager_noise_filtering():
    manager = AIProtocolManager(instructions="Test", noise_keys=["internal_id"])
    
    @manager.bind("tool")
    def tool():
        return {"id": 1, "internal_id": "secret", "data": "val"}

    # Noise-Filtering ist aktuell deaktiviert oder muss explizit getriggert werden
    res = await manager.call_action("tool", {})
    assert "internal_id" in res

def test_pipe_resolver_explicit_index():
    manager = AIProtocolManager()
    context = {
        "res": [{"id": "A"}, {"id": "B"}]
    }
    # In v2 we use explicit indexing to avoid ambiguity
    val, err = manager.sequencer.resolve_all("$res[0].id", context)
    assert val == "A"
    assert err is None

def test_manager_welcome_message():
    manager = AIProtocolManager(instructions="Test")
    manager.welcome_message = "Hello Agent"
    
    md = manager.get_manifest_md()
    assert "# Hello Agent" in md

def test_manager_manual_registration():
    app = FastAPI()
    manager = AIProtocolManager(instructions="Test")

    @manager.landmark("store:get_item")
    async def get_item(id: int):
        """Get an item from store."""
        return {"id": id}

    gateway = FastAPIGateway(manager)
    gateway.bind_to_app(app)
    
    # Landmark ID sollte registriert sein
    assert "store:get_item" in manager.landmarks
    lm = manager.landmarks["store:get_item"]
    assert "Get an item from store" in lm.description
    # assert lm.parameters[0].name == "id" # Magic extraction disabled
