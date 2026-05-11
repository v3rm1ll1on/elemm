import pytest
import httpx
import respx
import json
from unittest.mock import patch, mock_open
from elemm_gateway.server import ElemmGateway
import mcp.types as types

@pytest.fixture
def gateway():
    # Mock vault data
    mock_vault = {
        "api.weatherapi.com": {
            "type": "apiKey",
            "name": "key",
            "in": "query",
            "value": "V4ULT_K3Y"
        }
    }
    gw = ElemmGateway()
    gw.vault_manager.load = lambda: mock_vault # Direct override on component
    gw.vault_manager.vault = mock_vault
    return gw

@pytest.mark.asyncio
async def test_vault_key_injection(gateway):
    """Verify that API keys from vault are injected into query params for OpenAPI."""
    target_url = "https://api.weatherapi.com/openapi.json"
    
    with respx.mock:
        # 1. Mock the OpenAPI spec fetch
        respx.get(target_url).respond(
            status_code=200,
            json={
                "openapi": "3.0.0",
                "servers": [{"url": "https://api.weatherapi.com/v1"}],
                "paths": {
                    "/current.json": {
                        "get": {
                            "operationId": "getCurrentWeather",
                            "tags": ["Weather"],
                            "parameters": [
                                {"name": "key", "in": "query", "required": True},
                                {"name": "q", "in": "query", "required": True}
                            ]
                        }
                    }
                }
            }
        )
        
        # Connect
        res = await gateway._connect(target_url)
        print(f"Connect result: {res[0].text}")
        assert gateway.active_site_url == target_url, f"Failed to connect to {target_url}. Result: {res[0].text}"
        
        # 2. Mock the actual API call (flexible regex match for query params)
        import re
        route = respx.get(url__regex=re.compile(r".*/current\.json.*")).mock(
            return_value=httpx.Response(200, json={"temp": 20})
        )
        
        # Use execute_sequence
        actions = [
            {"action": "Weather_getCurrentWeather", "parameters": {"q": "Berlin"}}
        ]
        await gateway._handle_execute_sequence(actions)
        
        # Verify injection
        assert route.called
        # Check params on the first call to this route
        request = route.calls[0].request
        assert request.url.params["key"] == "V4ULT_K3Y"
        assert request.url.params["q"] == "Berlin"

@pytest.mark.asyncio
async def test_hygiene_squishing_nested(gateway):
    """Verify that _select correctly filters nested JSON structures."""
    target_url = "https://api.test.com/openapi.json"
    
    with respx.mock:
        respx.get(target_url).respond(status_code=200, json={
            "openapi": "3.0.0",
            "servers": [{"url": "https://api.test.com"}],
            "paths": {"/data": {"get": {"operationId": "getData"}}}
        })
        await gateway._connect(target_url)
        
        # Mock response
        respx.get("https://api.test.com/data").respond(
            status_code=200,
            json={
                "id": 1,
                "user": {"name": "Siddy", "role": "admin"}
            }
        )
        
        # Call via execute_sequence
        actions = [{"action": "General_getData", "parameters": {"_select": "user.name"}}]
        res = await gateway._handle_execute_sequence(actions)
        
        results = json.loads(res[0].text)
        assert results[0]["result"]["user"] == {"name": "Siddy"}
        assert "id" not in results[0]["result"]

@pytest.mark.asyncio
async def test_auth_remedy_standard(gateway):
    """Verify that 401 errors return the standardized Elemm Remedy format."""
    target_url = "https://api.locked.com/openapi.json"
    
    with respx.mock:
        respx.get(target_url).respond(status_code=200, json={
            "openapi": "3.0.0",
            "servers": [{"url": "https://api.locked.com"}],
            "paths": {"/secret": {"get": {"operationId": "getSecret"}}}
        })
        await gateway._connect(target_url)
        
        # Mock 401 Unauthorized
        respx.get("https://api.locked.com/secret").respond(status_code=401, text="Unauthorized")
        
        actions = [{"action": "General_getSecret"}]
        res = await gateway._handle_execute_sequence(actions)
        
        results = json.loads(res[0].text)
        error_data = results[0]["result"]
        assert error_data["status"] == "error"
        assert "remedy" in error_data
        assert "Authentication failed" in error_data["remedy"]

@pytest.mark.asyncio
async def test_landmark_discovery_grouping(gateway):
    """Verify that get_landmarks groups tools correctly."""
    target_url = "https://api.grouped.com/openapi.json"
    
    with respx.mock:
        respx.get(target_url).respond(status_code=200, json={
            "openapi": "3.0.0",
            "paths": {
                "/a": {"get": {"tags": ["A"], "operationId": "one"}},
                "/b": {"get": {"tags": ["A"], "operationId": "two"}}
            }
        })
        res = await gateway._connect(target_url)
        print(f"Grouped Connect result: {res[0].text}")
        assert gateway.active_site_url == target_url
        
        # Use core tool call
        res = await gateway._proxy_core_tool("get_landmarks", {})
        summary = res[0].text
        
        assert "- **A**: (2 tools)" in summary
