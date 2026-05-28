# Copyright (C) 2026 Marc Stöcker
# Website: https://elemm.dev
#
# This program is licensed under the Business Source License 1.1 (BSL 1.1).
# See the LICENSE file in the root directory for details.

import pytest
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Literal
from elemm.core.manager import AIProtocolManager
from elemm.core.models import Landmark
from elemm.gateways.fastapi import FastAPIGateway

class MockResponse(BaseModel):
    status: str
    data: int

def test_manager_binding_and_enrichment():
    manager = AIProtocolManager(instructions="Test instructions")
    
    @manager.landmark("test:action")
    def my_tool(name: str, age: int = 20) -> MockResponse:
        """My tool description."""
        return MockResponse(status="ok", data=age)

    # Prüfe ob Landmark registriert wurde
    assert "test:action" in manager.landmarks
    lm = manager.landmarks["test:action"]
    
    # Auto-Discovery check
    assert len(lm.parameters) == 2
    assert lm.parameters[0].name == "name"
    assert lm.parameters[0].type == "string"
    assert lm.parameters[1].name == "age"
    assert lm.parameters[1].type == "integer"
    assert lm.parameters[1].required is False
    assert lm.parameters[1].default == 20

    assert "My tool description" in lm.description

def test_manager_pydantic_discovery():
    manager = AIProtocolManager()

    class Item(BaseModel):
        id: int
        name: str

    @manager.landmark("store:add")
    def add_item(item: Item):
        return {"status": "added"}

    lm = manager.landmarks["store:add"]
    assert len(lm.parameters) == 2
    assert lm.parameters[0].name == "id"
    assert lm.parameters[0].type == "integer"
    assert lm.parameters[1].name == "name"
    assert lm.parameters[1].type == "string"

def test_manager_literal_discovery():
    manager = AIProtocolManager()

    @manager.landmark("light:set")
    def set_light(state: Literal["on", "off"]):
        return {"state": state}

    lm = manager.landmarks["light:set"]
    assert lm.parameters[0].type == "string"
    assert lm.parameters[0].options == ["on", "off"]

@pytest.mark.asyncio
async def test_manager_call_action():
    manager = AIProtocolManager()
    
    @manager.landmark("test:tool")
    def tool(q: str):
        return {"received": q}

    res = await manager.call_action("test:tool", {"q": "hello"})
    assert res["received"] == "hello"

def test_pipe_resolver_explicit_index():
    manager = AIProtocolManager()
    context = {
        "res": [{"id": "A"}, {"id": "B"}]
    }
    val, err = manager.sequencer.resolve_all("$res[0].id", context)
    assert val == "A"
    assert err is None

def test_manager_welcome_message():
    manager = AIProtocolManager()
    manager.welcome_message = "Hello Agent"
    
    md = manager.get_manifest()
    assert "# Hello Agent" in md


# --- Tests für manager.register() (neu in dieser Session hinzugefügt) ---

def test_register_creates_landmark_without_handler():
    """register() soll eine Landmarke ohne Handler erzeugen (rein navigatorisch)."""
    manager = AIProtocolManager()
    manager.register("Region:District", description="A navigation node")

    assert "Region:District" in manager.landmarks
    lm = manager.landmarks["Region:District"]
    assert lm.description == "A navigation node"
    assert lm.handler is None


def test_register_builds_parent_hierarchy():
    """register() soll auch alle Eltern-Knoten automatisch anlegen."""
    manager = AIProtocolManager()
    manager.register("A:B:C", description="Leaf node")

    assert "A" in manager.landmarks
    assert "A:B" in manager.landmarks
    assert "A:B:C" in manager.landmarks


def test_register_then_landmark_links_correctly():
    """register() für Parent + landmark() für Tool → Parent.tools muss das Tool enthalten."""
    manager = AIProtocolManager()

    manager.register("Nord:Sector_042", description="District node")
    manager.register("Nord:Sector_042:energy", description="Category node")

    @manager.landmark("Nord:Sector_042:energy:reroute_power", description="Reroute tool")
    def reroute(source: str, target: str):
        return {"status": "ok"}

    district = manager.landmarks["Nord:Sector_042"]
    category = manager.landmarks["Nord:Sector_042:energy"]
    tool = manager.landmarks["Nord:Sector_042:energy:reroute_power"]

    # Kategorie muss im District hängen
    assert any(t.id == "Nord:Sector_042:energy" for t in district.tools)
    # Tool muss in Kategorie hängen
    assert any(t.id == "Nord:Sector_042:energy:reroute_power" for t in category.tools)
    # Tool muss einen Handler haben, Eltern nicht
    assert tool.handler is not None
    assert district.handler is None
    assert category.handler is None


@pytest.mark.asyncio
async def test_register_namespace_call_returns_error():
    """call_action auf einen reinen register()-Knoten (kein Handler) soll einen klaren Fehler liefern."""
    manager = AIProtocolManager()
    manager.register("Region:District", description="Navigation only")

    result = await manager.call_action("Region:District", {})
    assert result["status"] == "error"