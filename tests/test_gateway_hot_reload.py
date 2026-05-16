# Copyright (C) 2026 Marc Stöcker
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import pytest
import json
import os
import time
import tempfile
from elemm_gateway.server import ElemmGateway

@pytest.fixture
def temp_config():
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        json.dump({
            "security": {
                "disallowed_patterns": ["delete"],
                "allowed_methods": ["GET", "POST"]
            }
        }, f)
        config_path = f.name
    
    yield config_path
    
    if os.path.exists(config_path):
        os.remove(config_path)

@pytest.mark.asyncio
async def test_hot_reload_disallowed_patterns(temp_config):
    """Verify that changing the config file affects the gateway instantly."""
    # 1. Initialize gateway with the temp config
    gw = ElemmGateway()
    gw.config_manager.config_path = temp_config
    gw.config_manager.last_mtime = 0
    gw.config_manager.config = gw.config_manager.load()
    gw.security_policy.refresh(gw.config_manager.config)
    
    # Authorize for test
    gw.manifest_loaded = True
    gw.active_site_url = "https://test-api.com"
    
    # Check if 'delete' is blocked
    res = await gw._execute_single("delete_user", {})
    assert "ACCESS_DENIED" in res
    
    # Check if 'create' is allowed
    res = await gw._execute_single("create_user", {})
    assert "ACCESS_DENIED" not in res 
    
    # 2. Update config file to block 'create' as well
    # Ensure mtime changes by waiting a bit
    time.sleep(0.1)
    with open(temp_config, "w") as f:
        json.dump({
            "security": {
                "disallowed_patterns": ["delete", "create"],
                "allowed_methods": ["GET", "POST"]
            }
        }, f)
    
    # 3. Call tool through _handle_call_tool (which triggers reload)
    # This should reload the config before executing
    await gw._handle_call_tool("call_action", {"action": "some_tool", "parameters": {}})
    
    # 4. Now 'create' should also be blocked
    res = await gw._execute_single("create_user", {})
    assert "ACCESS_DENIED" in res
    assert "pattern 'create'" in res

@pytest.mark.asyncio
async def test_hot_reload_landmark_blocking(temp_config):
    """Verify that landmark blocking can be updated on the fly."""
    gw = ElemmGateway()
    gw.config_manager.config_path = temp_config
    gw.config_manager.last_mtime = 0
    gw.config_manager.config = gw.config_manager.load()
    gw.security_policy.refresh(gw.config_manager.config)
    gw.manifest_loaded = True
    gw.active_site_url = "https://test-api.com"
    
    # Initially 'admin' landmark is not blocked
    res = await gw._execute_single("admin:reset", {})
    assert "ACCESS_DENIED" not in res
    
    # Update config to block 'admin'
    time.sleep(0.1)
    with open(temp_config, "w") as f:
        json.dump({
            "security": {
                "disallowed_landmarks": ["admin"]
            }
        }, f)
        
    # Trigger reload
    await gw._handle_call_tool("call_action", {"action": "some_tool", "parameters": {}})
    
    # Now 'admin' should be blocked
    res = await gw._execute_single("admin:reset", {})
    assert "ACCESS_DENIED" in res
    assert "Landmark area 'admin' within path is restricted" in res

@pytest.mark.asyncio
async def test_hot_reload_manifest_filtering(temp_config):
    """Verify that blocked landmarks are removed from the full manifest string."""
    gw = ElemmGateway()
    gw.config_manager.config_path = temp_config
    gw.config_manager.last_mtime = 0
    gw.config_manager.config = gw.config_manager.load()
    gw.security_policy.refresh(gw.config_manager.config)
    
    # Mock site data with two landmarks
    gw.active_site_url = "https://test-api.com"
    gw.connected_sites[gw.active_site_url] = {
        "type": "openapi",
        "landmarks": [
            {"id": "Geo:get", "name": "Geo:get", "description": "Geo tool", "parameters": []},
            {"id": "Public:info", "name": "Public:info", "description": "Public tool", "parameters": []}
        ]
    }
    gw.manifest_loaded = True
    
    # 1. Initially both are visible in manifest
    res = await gw._handle_call_tool("get_manifest", {})
    manifest_text = res[0].text
    assert "Geo:get" in manifest_text
    assert "Public:info" in manifest_text
    
    # 2. Block 'Geo'
    time.sleep(0.1)
    with open(temp_config, "w") as f:
        json.dump({"security": {"disallowed_landmarks": ["Geo"]}}, f)
        
    # 3. Call get_manifest again (triggers reload + filtering)
    res = await gw._handle_call_tool("get_manifest", {})
    manifest_text = res[0].text
    
    # 4. 'Geo' must be gone, 'Public' must remain
    assert "Geo:get" not in manifest_text
    assert "Public:info" in manifest_text

@pytest.mark.asyncio
async def test_hot_reload_inspect_blocking(temp_config):
    """Verify that inspection of blocked landmarks is rejected."""
    gw = ElemmGateway()
    gw.config_manager.config_path = temp_config
    gw.config_manager.last_mtime = 0
    gw.config_manager.config = gw.config_manager.load()
    gw.security_policy.refresh(gw.config_manager.config)
    
    gw.active_site_url = "https://test-api.com"
    gw.connected_sites[gw.active_site_url] = {
        "type": "openapi",
        "landmarks": [{"id": "Admin:config", "name": "Admin:config", "description": "Admin tool", "parameters": []}]
    }
    gw.manifest_loaded = True
    
    # 1. Block 'Admin'
    time.sleep(0.1)
    with open(temp_config, "w") as f:
        json.dump({"security": {"disallowed_landmarks": ["Admin"]}}, f)
        
    # 2. Try to inspect 'Admin' (triggers reload + security check)
    res = await gw._handle_call_tool("inspect_landmark", {"landmark_id": "Admin"})
    
    # 3. Must be blocked
    assert "ACCESS_DENIED" in res[0].text
    assert "Access to 'Admin' is restricted" in res[0].text

@pytest.mark.asyncio
async def test_hot_reload_short_action_blocking(temp_config):
    """Verify that blocking a short action name blocks it even with a namespace."""
    gw = ElemmGateway()
    gw.config_manager.config_path = temp_config
    gw.config_manager.last_mtime = 0
    gw.config_manager.config = gw.config_manager.load()
    gw.security_policy.refresh(gw.config_manager.config)
    gw.manifest_loaded = True
    gw.active_site_url = "https://test-api.com"
    
    # 1. Block just 'get_secret' (not the full 'Geo:get_secret')
    time.sleep(0.1)
    with open(temp_config, "w") as f:
        json.dump({"security": {"disallowed_actions": ["get_secret"]}}, f)
        
    # Trigger reload
    await gw._handle_call_tool("call_action", {"action": "some_tool", "parameters": {}})
    
    # 2. Try to call 'Geo:get_secret'
    res = await gw._execute_single("Geo:get_secret", {})
    
    # 3. Must be blocked because the short name matches
    assert "ACCESS_DENIED" in res
    assert "explicitly blacklisted" in res

@pytest.mark.asyncio
async def test_hot_reload_nested_landmark_blocking(temp_config):
    """Verify that blocking a middle segment of a nested landmark path works."""
    gw = ElemmGateway()
    gw.config_manager.config_path = temp_config
    gw.config_manager.last_mtime = 0
    gw.config_manager.config = gw.config_manager.load()
    gw.security_policy.refresh(gw.config_manager.config)
    gw.manifest_loaded = True
    gw.active_site_url = "https://test-api.com"
    
    # 1. Block 'Internal' (the middle segment of 'Root:Internal:Tool')
    time.sleep(0.1)
    with open(temp_config, "w") as f:
        json.dump({"security": {"disallowed_landmarks": ["internal"]}}, f)
        
    # Trigger reload
    await gw._handle_call_tool("call_action", {"action": "some_tool", "parameters": {}})
    
    # 2. Try to call the nested path
    res = await gw._execute_single("Root:Internal:Tool", {})
    
    # 3. Must be blocked because 'Internal' is in the path
    assert "ACCESS_DENIED" in res
    assert "Landmark area 'internal' within path is restricted" in res

@pytest.mark.asyncio
async def test_hot_reload_http_methods(temp_config):
    """Verify that HTTP method restrictions can be updated on the fly."""
    gw = ElemmGateway()
    gw.config_manager.config_path = temp_config
    gw.config_manager.last_mtime = 0
    gw.config_manager.config = gw.config_manager.load()
    gw.security_policy.refresh(gw.config_manager.config)
    gw.manifest_loaded = True
    gw.active_site_url = "https://test-api.com"
    
    # Mock site data with method info
    gw.connected_sites[gw.active_site_url] = {
        "type": "openapi",
        "landmarks": [{"id": "update_user", "meta": {"method": "POST"}}]
    }
    
    # Initially POST is allowed
    res = await gw._execute_single("update_user", {})
    assert "ACCESS_DENIED" not in res
    
    # Update config to allow only GET
    time.sleep(0.1)
    with open(temp_config, "w") as f:
        json.dump({"security": {"allowed_methods": ["GET"]}}, f)
        
    # Trigger reload
    await gw._handle_call_tool("call_action", {"action": "some_tool", "parameters": {}})
    
    # Now POST should be blocked
    res = await gw._execute_single("update_user", {})
    assert "ACCESS_DENIED" in res
    assert "method 'POST' is restricted" in res

@pytest.mark.asyncio
async def test_hot_reload_limits(temp_config):
    """Verify that response size limits can be updated on the fly."""
    gw = ElemmGateway()
    gw.config_manager.config_path = temp_config
    gw.config_manager.last_mtime = 0
    gw.config_manager.config = gw.config_manager.load()
    gw.security_policy.refresh(gw.config_manager.config)
    
    assert gw.limit_standard == 30000 # Default
    
    # Update config limit
    time.sleep(0.1)
    with open(temp_config, "w") as f:
        json.dump({"limit_standard": 500}, f)
        
    # Trigger reload
    await gw._handle_call_tool("call_action", {"action": "some_tool", "parameters": {}})
    
    assert gw.limit_standard == 500

@pytest.mark.asyncio
async def test_resilience_corrupted_config(temp_config):
    """Verify that the gateway survives a corrupted (invalid JSON) config file."""
    gw = ElemmGateway()
    gw.config_manager.config_path = temp_config
    gw.config_manager.last_mtime = 0
    gw.config_manager.config = gw.config_manager.load()
    
    original_config = gw.config_manager.config.copy()
    
    # Corrupt the config file
    time.sleep(0.1)
    with open(temp_config, "w") as f:
        f.write("{ invalid json: [")
        
    # Trigger reload
    # Should log an error but NOT crash and keep old config or defaults
    reloaded = gw.config_manager.reload_if_changed()
    
    assert reloaded is True # It tried to reload
    # ConfigManager.load returns defaults on error, so it should still be a valid dict
    assert isinstance(gw.config_manager.config, dict)
    assert "security" in gw.config_manager.config
