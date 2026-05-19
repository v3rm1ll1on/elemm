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
import json
import re
from unittest.mock import MagicMock, AsyncMock, patch
from elemm_gateway.components import GraphQLExecutor, OpenAPIExecutor, VaultManager
from elemm_gateway.server import ElemmGateway

@pytest.mark.asyncio
async def test_graphql_nesting_remedy():
    """Tests if cryptic GQL nesting errors are translated to Elemm remedies."""
    executor = GraphQLExecutor(MagicMock(spec=VaultManager))
    
    # Mock a 400 response with a nesting error
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.json.return_value = {
        "errors": [{"message": 'Field "origin" of type "Location" must have a selection of subfields. Did you mean "origin { ... }"'}]
    }
    
    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        res_str = await executor.execute({"meta": {"field_name": "test"}}, {"id": "1"})
        res = json.loads(res_str)
        
        assert res["status"] == "error"
        assert "dot-notation" in res["remedy"]
        assert "origin" in res["remedy"]

@pytest.mark.asyncio
async def test_openapi_error_details_extraction():
    """Tests if details are extracted from OpenAPI 400 responses."""
    executor = OpenAPIExecutor(MagicMock(spec=VaultManager))
    
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.json.return_value = {"message": "Invalid date format. Use YYYY-MM-DD."}
    
    with patch("httpx.AsyncClient.request", return_value=mock_resp):
        res_str = await executor.execute({"meta": {"base_url": "http://api", "path": "/test"}}, {"q": "val"})
        res = json.loads(res_str)
        
        assert res["status"] == "error"
        assert "Invalid date format" in res["message"]
        assert "inspect_landmark" in res["remedy"]

@pytest.mark.asyncio
async def test_empty_result_info_injection():
    """Tests if successful but empty results get an _INFO hint."""
    executor = OpenAPIExecutor(MagicMock(spec=VaultManager))
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = []
    
    with patch("httpx.AsyncClient.request", return_value=mock_resp):
        res_str = await executor.execute({"meta": {"base_url": "http://api", "path": "/test"}}, {"q": "val"})
        res = json.loads(res_str)
        
        assert res["status"] == "success"
        assert "_INFO" in res
        assert "returned no results" in res["_INFO"]

@pytest.mark.asyncio
async def test_landmark_namespace_protection_remedy():
    """Tests if calling a Landmark instead of a tool triggers a structural error."""
    gateway = ElemmGateway()
    gateway.active_site_url = "http://test-site"
    gateway.connected_sites["http://test-site"] = {
        "type": "openapi",
        "tools": [
            {"name": "Weather_get", "meta": {"type": "openapi"}},
            {"name": "Weather_list", "meta": {"type": "openapi"}}
        ]
    }
    
    gateway.manifest_loaded = True
    
    # We call 'Weather' which is a landmark (prefix of Weather_get)
    res_str = await gateway._execute_openapi("Weather", {})
    res = json.loads(res_str)
    
    assert "STRUCTURAL ERROR" in res["message"]
    assert "Landmark Namespace" in res["message"]
    assert "inspect_landmark" in res["remedy"]

@pytest.mark.asyncio
async def test_vault_hot_reload():
    """Tests if the vault is reloaded on each connect without server restart."""
    with patch("os.path.expanduser", return_value="/tmp/elemm"):
        vault_manager = VaultManager("/tmp/elemm/vault.json")
        gateway = ElemmGateway()
        gateway.vault_manager = vault_manager
        
        # 1. Initial empty vault
        with patch.object(VaultManager, "load", return_value={}):
            await gateway._connect("https://api.test")
            assert gateway.vault_manager.vault == {}
            
        # 2. Vault updated (simulating file change)
        with patch.object(VaultManager, "load", return_value={"api.test": "secret-key"}):
            await gateway._connect("https://api.test")
            assert gateway.vault_manager.vault == {"api.test": "secret-key"}

@pytest.mark.asyncio
async def test_malformed_piping_syntax():
    """Tests if malformed piping paths like $step0.wrong are handled gracefully."""
    from elemm_gateway.components import SequenceEngine
    gateway = ElemmGateway()
    engine = SequenceEngine(gateway)
    engine.aliases = {"step0": {"user": {"name": "Rick"}}}
    
    # Non-existent field
    with pytest.raises(ValueError) as excinfo:
        engine._navigate(engine.aliases["step0"], "user.status", engine.aliases)
    assert "Path component 'status' failed" in str(excinfo.value)
    assert "name" in str(excinfo.value)


@pytest.mark.asyncio
async def test_disconnected_structured_remedy():
    """Verify that calling execution when disconnected returns a structured DISCONNECTED error with remedy."""
    gateway = ElemmGateway()
    gateway.active_site_url = None
    res_str = await gateway._execute_single("some_tool", {})
    res = json.loads(res_str)
    assert res["status"] == "error"
    assert res["_PROTOCOL_ERROR"] == "DISCONNECTED"
    assert "remedy" in res
    assert "example" in res
    assert "connect_to_site" in res["example"]


@pytest.mark.asyncio
async def test_protocol_violation_structured_remedy():
    """Verify that calling execution before loading manifest returns a PROTOCOL_VIOLATION error with remedy."""
    gateway = ElemmGateway()
    gateway.active_site_url = "http://test-site"
    gateway.manifest_loaded = False
    res_str = await gateway._execute_single("some_tool", {})
    res = json.loads(res_str)
    assert res["status"] == "error"
    assert res["_PROTOCOL_ERROR"] == "PROTOCOL_VIOLATION"
    assert "remedy" in res
    assert "example" in res
    assert "get_manifest" in res["example"]


@pytest.mark.asyncio
async def test_tool_not_found_fuzzy_remedy():
    """Verify that calling a non-existent tool returns a fuzzy match suggestion via SmartRepairEngine."""
    gateway = ElemmGateway()
    gateway.active_site_url = "http://test-site"
    gateway.connected_sites["http://test-site"] = {
        "type": "openapi",
        "tools": [
            {"name": "Weather_get", "meta": {"type": "openapi"}},
            {"name": "Weather_list", "meta": {"type": "openapi"}}
        ]
    }
    gateway.manifest_loaded = True

    # Call with a spelling mistake
    res_str = await gateway._execute_openapi("Weather_gut", {})
    res = json.loads(res_str)
    assert res["status"] == "error"
    assert res["_PROTOCOL_ERROR"] == "NOT_FOUND"
    assert "remedy" in res
    assert "Weather_get" in res["remedy"]


