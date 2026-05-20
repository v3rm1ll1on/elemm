# Copyright (C) 2026 Marc Stöcker
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import pytest
import os
import yaml
import tempfile
from unittest.mock import AsyncMock, patch, MagicMock

from elemm.core.models import Landmark, Parameter
from elemm_gateway.services.manifest_service import ManifestService

@pytest.mark.asyncio
async def test_inspect_mcp_local_support():
    """Tests that ManifestService.inspect_url correctly handles mcp://local by discovering local MCP servers."""
    
    # Mock Landmark returned by MCPBridge
    mock_lm = Landmark(
        id="mcp:test-server:get_items",
        type="action",
        description="Retrieve items",
        instructions="",
        tools=[],
        parameters=[
            Parameter(name="query", type="string", required=True, description="search query", location="body")
        ],
        returns="any",
        meta={"method": "mcp"}
    )

    with patch("elemm_gateway.services.mcp_config.MCPConfigManager") as MockConfigClass, \
         patch("elemm_gateway.services.mcp_bridge.MCPBridge") as MockBridgeClass:
        
        # Mock Config Manager
        mock_config = MagicMock()
        mock_config.get_servers.return_value = {
            "test-server": {
                "name": "Test Server",
                "description": "Mocked test server",
                "transport": "stdio",
                "command": "python3"
            }
        }
        MockConfigClass.return_value = mock_config
        
        # Mock Bridge
        mock_bridge = MagicMock()
        mock_bridge.discover_landmarks = AsyncMock(return_value=[mock_lm])
        mock_bridge.process_manager = AsyncMock()
        mock_bridge.process_manager.stop_all = AsyncMock()
        MockBridgeClass.return_value = mock_bridge
        
        # Call ManifestService.inspect_url with 'mcp://local'
        res = await ManifestService.inspect_url("mcp://local", output_format="json")
        
        # Asserts
        assert res["status"] == "success"
        assert res["type"] == "native"
        assert res["url"] == "mcp://local"
        
        data = res["data"]
        assert data["title"] == "Local MCP Environment"
        assert data["type"] == "native"
        
        landmarks = data["landmarks"]
        assert len(landmarks) == 2  # 1 navigation + 1 action landmark
        
        nav = next(lm for lm in landmarks if lm["type"] == "navigation")
        assert nav["id"] == "mcp:test-server"
        assert nav["description"] == "Mocked test server"
        
        action = next(lm for lm in landmarks if lm["type"] == "action")
        assert action["id"] == "mcp:test-server:get_items"
        assert action["description"] == "Retrieve items"
        assert len(action["parameters"]) == 1
        assert action["parameters"][0]["name"] == "query"
        
        # Verify bridge methods were called
        mock_bridge.discover_landmarks.assert_called_once_with("test-server", vault_manager=None)
        mock_bridge.process_manager.stop_all.assert_called_once()
