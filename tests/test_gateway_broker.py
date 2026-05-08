import pytest
import httpx
import respx
import json
from elemm_gateway.server import ElemmGateway
import mcp.types as types

@pytest.mark.asyncio
async def test_gateway_broker_connect_and_proxy():
    gateway = ElemmGateway()
    target_url = "http://mock-site:8000"
    
    with respx.mock:
        # Mock Manifest (Discovery)
        manifest_url = f"{target_url}/.well-known/elemm-manifest.md?technical=true"
        respx.get(manifest_url).respond(
            status_code=200,
            text="### AGENT DIRECTIVE\nTest directive\n```json-elemm\n{\"version\": \"1.0.0\", \"landmarks\": []}\n```"
        )
        
        # Mock Action Call
        respx.post(f"{target_url}/.well-known/elemm/execute").respond(
            status_code=200,
            json={"status": "ok", "data": "proxied_data"}
        )

        # 1. Test Connect
        res = await gateway._handle_call_tool("connect_to_site", {"url": target_url})
        assert "Connected to http://mock-site:8000" in res[0].text
        assert gateway.active_site_url == target_url

        # 2. Test Get Manifest (Proxied)
        res = await gateway._handle_call_tool("get_manifest", {})
        assert "AGENT DIRECTIVE" in res[0].text

        # 3. Test Call Action (Proxied)
        res = await gateway._handle_call_tool("call_action", {"action": "test_tool", "parameters": {}})
        assert "proxied_data" in res[0].text

@pytest.mark.asyncio
async def test_gateway_broker_error_handling():
    gateway = ElemmGateway()
    target_url = "http://offline-site:8000"
    
    with respx.mock:
        # Simulate connection error
        respx.get(f"{target_url}/.well-known/elemm-manifest.md?technical=true").mock(side_effect=httpx.ConnectError("Connection refused"))
        
        res = await gateway._handle_call_tool("connect_to_site", {"url": target_url})
        assert "Failed to find Elemm manifest" in res[0].text or "Connection refused" in res[0].text
