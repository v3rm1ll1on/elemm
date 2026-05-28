# Copyright (C) 2026 Marc Stöcker
# Website: https://elemm.dev
#
# This program is licensed under the Business Source License 1.1 (BSL 1.1).
# See the LICENSE file in the root directory for details.

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
        # Mock Manifest (Discovery) - Lazy Loading Pattern
        manifest_url = f"{target_url}/.well-known/elemm-manifest.md"
        respx.get(manifest_url).respond(
            status_code=200,
            text="### PROTOCOL RULES\nTest directive\n### LANDMARK TOPOLOGY\n- **test**: Area test\n"
        )
        
        # Mock Action Call (v2 Standard Endpoint)
        def exec_handler(request):
            body = json.loads(request.content)
            action = body.get("action")
            return httpx.Response(200, json={"status": "ok", "result": f"result_for_{action}"})
            
        respx.post(f"{target_url}/.well-known/elemm/execute").mock(side_effect=exec_handler)

        # 1. Test Connect
        res = await gateway._handle_call_tool("connect_to_site", {"url": target_url})
        assert "CONNECTED to" in res[0].text and target_url in res[0].text
        assert gateway.active_site_url == target_url

        # 2. Test Get Manifest (Proxied)
        res = await gateway._handle_call_tool("get_manifest", {})
        assert "PROTOCOL WORKFLOW" in res[0].text
        assert "SESSION GOVERNANCE" in res[0].text
        assert "test" in res[0].text
        assert "Area test" in res[0].text

        # 3. Test Call Action (Proxied)
        res = await gateway._handle_call_tool("call_action", {"action": "test_tool", "parameters": {}})
        assert "result_for_test_tool" in res[0].text

@pytest.mark.asyncio
async def test_gateway_broker_error_handling():
    gateway = ElemmGateway()
    target_url = "http://offline-site:8000"
    
    with respx.mock:
        # Simulate connection error
        respx.get(f"{target_url}/.well-known/elemm-manifest.md").mock(side_effect=httpx.ConnectError("Connection refused"))
        
        res = await gateway._handle_call_tool("connect_to_site", {"url": target_url})
        assert any(word in res[0].text for word in ["Failed", "Error", "Connection refused"])

@pytest.mark.asyncio
async def test_gateway_broker_connect_with_manifest():
    gateway = ElemmGateway()
    target_url = "http://mock-site:8000"
    
    with respx.mock:
        # Mock Manifest (Discovery) - Lazy Loading Pattern
        manifest_url = f"{target_url}/.well-known/elemm-manifest.md"
        respx.get(manifest_url).respond(
            status_code=200,
            text="### PROTOCOL RULES\nTest directive\n### LANDMARK TOPOLOGY\n- **test**: Area test\n"
        )
        
        # Test Connect mit get_manifest=True
        res = await gateway._handle_call_tool("connect_to_site", {"url": target_url, "get_manifest": True})
        # Das Ergebnis sollte direkt das Manifest sein, nicht die Standard-Erfolgsmeldung
        assert "PROTOCOL WORKFLOW" in res[0].text
        assert "SESSION GOVERNANCE" in res[0].text
        assert "test" in res[0].text
        assert "Area test" in res[0].text
        assert gateway.manifest_loaded is True

@pytest.mark.asyncio
async def test_gateway_broker_connect_with_config_manifest():
    gateway = ElemmGateway()
    gateway.config_manager.config["auto_get_manifest"] = True
    target_url = "http://mock-site:8000"
    
    with respx.mock:
        manifest_url = f"{target_url}/.well-known/elemm-manifest.md"
        respx.get(manifest_url).respond(
            status_code=200,
            text="### PROTOCOL RULES\nTest directive\n### LANDMARK TOPOLOGY\n- **test**: Area test\n"
        )
        
        res = await gateway._handle_call_tool("connect_to_site", {"url": target_url})
        assert "PROTOCOL WORKFLOW" in res[0].text
        assert "test" in res[0].text
        assert gateway.manifest_loaded is True