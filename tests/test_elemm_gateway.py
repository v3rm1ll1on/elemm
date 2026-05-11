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
from elemm import ElemmGateway

def test_gateway_initialization():
    gw = ElemmGateway(name="TestGateway", instructions="Custom Instructions")
    assert gw.name == "TestGateway"
    assert gw.manager.instructions == "Custom Instructions"
    assert "TestGateway" in gw.manager.welcome_message

@pytest.mark.asyncio
async def test_action_auto_prefixing():
    gw = ElemmGateway()
    
    @gw.action(landmark="Security")
    async def lock_door(door_id: str):
        return {"status": "locked", "id": door_id}
    
    # Check if tool is registered with auto-prefixed ID
    assert "Security:lock_door" in gw.manager.landmarks
    
    # Test execution
    res = await gw.manager.call_action("Security:lock_door", {"door_id": "D1"})
    assert res["status"] == "locked"
    assert res["id"] == "D1"

@pytest.mark.asyncio
async def test_action_explicit_id():
    gw = ElemmGateway()
    
    @gw.action(landmark="custom:id")
    async def my_func():
        return "ok"
    
    assert "custom:id" in gw.manager.landmarks
    assert "custom:my_func" not in gw.manager.landmarks
    
    res = await gw.manager.call_action("custom:id", {})
    assert res == "ok"

def test_load_metadata_delegation(tmp_path):
    # Mocking metadata loading
    yaml_file = tmp_path / "meta.yaml"
    yaml_file.write_text("landmarks: { test: { description: 'Updated' } }")
    
    gw = ElemmGateway()
    gw.load_metadata(str(yaml_file))
    
    # Trigger registry update (usually happens on registration or manual call)
    # Registry is internal to manager
    assert gw.manager.registry.get("test").description == "Updated"
