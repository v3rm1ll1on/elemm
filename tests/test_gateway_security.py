# Copyright (C) 2026 Marc Stöcker
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import pytest
import json
import respx
import httpx
from elemm_gateway.server import ElemmGateway
from elemm_gateway.components import SecurityPolicy

@pytest.fixture
def gateway():
    gw = ElemmGateway()
    # Mock a basic security config
    gw.security_policy = SecurityPolicy({
        "security": {
            "disallowed_patterns": ["delete", "remove"],
            "disallowed_landmarks": ["admin"],
            "allowed_methods": ["GET", "POST"]
        }
    })
    return gw

@pytest.mark.asyncio
async def test_protocol_violation_enforcement(gateway):
    """Verify that actions are blocked if get_manifest was not called."""
    target_url = "https://api.test.com/openapi.json"
    
    with respx.mock:
        respx.get(target_url).respond(status_code=200, json={
            "openapi": "3.0.0",
            "paths": {"/data": {"get": {"operationId": "getData"}}}
        })
        
        # Connect (sets manifest_loaded=False)
        await gateway._connect(target_url)
        assert gateway.manifest_loaded is False
        
        # Try to call action directly
        res = await gateway._execute_single("General_getData", {})
        data = json.loads(res)
        
        assert data["status"] == "error"
        assert data["_PROTOCOL_ERROR"] == "PROTOCOL_VIOLATION"

@pytest.mark.asyncio
async def test_handshake_authorizes_session(gateway):
    """Verify that calling get_manifest authorizes the session."""
    target_url = "https://api.test.com/openapi.json"
    
    with respx.mock:
        respx.get(target_url).respond(status_code=200, json={
            "openapi": "3.0.0",
            "paths": {"/data": {"get": {"operationId": "getData"}}}
        })
        await gateway._connect(target_url)
        assert gateway.manifest_loaded is False
        
        # Handshake
        await gateway._proxy_core_tool("get_manifest", {})
        assert gateway.manifest_loaded is True

@pytest.mark.asyncio
async def test_landmark_discovery_filtering(gateway):
    """Verify that restricted landmarks are hidden from get_landmarks."""
    target_url = "https://api.test.com/openapi.json"
    
    with respx.mock:
        respx.get(target_url).respond(status_code=200, json={
            "openapi": "3.0.0",
            "paths": {
                "/public": {"get": {"tags": ["public"], "operationId": "pub"}},
                "/private": {"get": {"tags": ["admin"], "operationId": "priv"}}
            }
        })
        await gateway._connect(target_url)
        gateway.manifest_loaded = True # Authorize
        
        # Re-inject policy to be sure it's active after connect
        gateway.security_policy = SecurityPolicy({
            "security": {
                "disallowed_landmarks": ["admin"],
                "allowed_methods": ["GET", "POST"]
            }
        })
        
        # Check landmarks
        res = await gateway._proxy_core_tool("get_landmarks", {})
        summary = res[0].text
        
        assert "public" in summary
        assert "admin" not in summary

@pytest.mark.asyncio
async def test_pattern_blocking_execution(gateway):
    """Verify that actions containing blocked patterns are rejected."""
    target_url = "https://api.test.com/openapi.json"
    
    with respx.mock:
        respx.get(target_url).respond(status_code=200, json={
            "openapi": "3.0.0",
            "paths": {"/delete-user": {"post": {"operationId": "deleteUser"}}}
        })
        await gateway._connect(target_url)
        gateway.manifest_loaded = True # Authorize
        
        # Re-inject policy
        gateway.security_policy = SecurityPolicy({
            "security": {
                "disallowed_patterns": ["delete"],
                "allowed_methods": ["GET", "POST"]
            }
        })
        
        # Try to call delete action
        res = await gateway._execute_single("General_deleteUser", {})
        data = json.loads(res)
        
        assert data["status"] == "error"
        assert data["_PROTOCOL_ERROR"] == "ACCESS_DENIED"
        assert "pattern 'delete'" in data["message"]

@pytest.mark.asyncio
async def test_http_method_restriction(gateway):
    """Verify that restricted HTTP methods are blocked."""
    # Connect first
    target_url = "https://api.test.com/openapi.json"
    with respx.mock:
        respx.get(target_url).respond(status_code=200, json={
            "openapi": "3.0.0",
            "paths": {"/update": {"post": {"operationId": "updateData"}}}
        })
        await gateway._connect(target_url)
        gateway.manifest_loaded = True # Authorize
        
        # Set policy to GET only
        gateway.security_policy = SecurityPolicy({
            "security": {
                "allowed_methods": ["GET"]
            }
        })
        
        # POST should be blocked
        res = await gateway._execute_single("General_updateData", {})
        data = json.loads(res)
        
        assert data["status"] == "error"
        assert "method 'POST' is restricted" in data["message"]
