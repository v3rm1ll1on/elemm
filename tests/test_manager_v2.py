# Copyright (C) 2026 Marc Stöcker
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

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
    
    md = manager.get_manifest_md()
    assert "# Hello Agent" in md
