# Copyright (C) 2026 Marc Stöcker
# Website: https://elemm.dev
#
# This program is licensed under the Business Source License 1.1 (BSL 1.1).
# See the LICENSE file in the root directory for details.

import pytest
import os
import yaml
import tempfile
from unittest.mock import AsyncMock, patch, MagicMock

import mcp.types as mcp_types
from elemm_gateway.services.mcp_config import MCPConfigManager
from elemm_gateway.services.mcp_bridge import MCPBridge, MCPProcessManager

@pytest.mark.asyncio
async def test_mcp_bridge_discovery():
    """Tests if MCPBridge discovers external tools and translates them to Landmarks correctly."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = os.path.join(tmp_dir, "mcp_servers.yaml")
        config_data = {
            "version": "1.0",
            "servers": {
                "demo": {
                    "name": "Demo Server",
                    "transport": "stdio",
                    "command": "python3",
                    "args": ["-m", "demo"],
                    "remedies": {
                        "test_tool": "Das ist ein spezifisches Tool-Remedy."
                    }
                }
            }
        }
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config_data, f)

        config_manager = MCPConfigManager(config_path)
        
        # Create mock tools returned by the mcp server
        mock_tool = MagicMock(spec=mcp_types.Tool)
        mock_tool.name = "test_tool"
        mock_tool.description = "Schnittstelle zum Testen"
        mock_tool.inputSchema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Der Benutzername"},
                "age": {"type": "integer", "description": "Alter"}
            },
            "required": ["name"]
        }
        
        mock_tools_result = MagicMock()
        mock_tools_result.tools = [mock_tool]
        
        mock_session = AsyncMock()
        mock_session.list_tools.return_value = mock_tools_result
        
        mock_process_manager = AsyncMock(spec=MCPProcessManager)
        mock_process_manager.get_session.return_value = mock_session
        
        bridge = MCPBridge(config_manager, mock_process_manager)
        
        landmarks = await bridge.discover_landmarks("demo")
        
        assert len(landmarks) == 1
        lm = landmarks[0]
        assert lm.id == "mcp:demo:test_tool"
        assert lm.type == "action"
        assert lm.description == "Schnittstelle zum Testen"
        assert lm.remedy == "Das ist ein spezifisches Tool-Remedy."
        
        # Assert parameters
        assert len(lm.parameters) == 2
        p_name = next(p for p in lm.parameters if p.name == "name")
        p_age = next(p for p in lm.parameters if p.name == "age")
        
        assert p_name.type == "string"
        assert p_name.required is True
        assert p_age.type == "integer"
        assert p_age.required is False

@pytest.mark.asyncio
async def test_mcp_bridge_tool_call():
    """Tests if MCPBridge forwards the call_tool command to the mocked mcp session."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = os.path.join(tmp_dir, "mcp_servers.yaml")
        config_data = {
            "version": "1.0",
            "servers": {
                "demo": {
                    "name": "Demo Server",
                    "transport": "stdio",
                    "command": "python3",
                    "args": []
                }
            }
        }
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config_data, f)

        config_manager = MCPConfigManager(config_path)
        
        # Mock mcp.types.CallToolResult content
        mock_text_content = MagicMock()
        mock_text_content.text = "Das ist das Tool-Ergebnis!"
        
        mock_call_result = MagicMock()
        mock_call_result.content = [mock_text_content]
        
        mock_session = AsyncMock()
        mock_session.call_tool.return_value = mock_call_result
        
        mock_process_manager = AsyncMock(spec=MCPProcessManager)
        mock_process_manager.get_session.return_value = mock_session
        
        bridge = MCPBridge(config_manager, mock_process_manager)
        
        res = await bridge.call_tool("demo", "test_tool", {"param": "val"})
        
        assert res == "Das ist das Tool-Ergebnis!"
        mock_session.call_tool.assert_called_once_with("test_tool", {"param": "val"})


@pytest.mark.asyncio
async def test_mcp_bridge_tool_call_error():
    """Tests if MCPBridge raises RuntimeError when the tool execution returns isError=True."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = os.path.join(tmp_dir, "mcp_servers.yaml")
        config_data = {
            "version": "1.0",
            "servers": {
                "demo": {
                    "name": "Demo Server",
                    "transport": "stdio",
                    "command": "python3",
                    "args": []
                }
            }
        }
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config_data, f)

        config_manager = MCPConfigManager(config_path)
        
        mock_text_content = MagicMock()
        mock_text_content.text = "Etwas ging schief!"
        
        mock_call_result = MagicMock()
        mock_call_result.content = [mock_text_content]
        # explicitly set isError to True and bypass MagicMock auto-creation
        mock_call_result.isError = True
        mock_call_result.is_error = True
        
        mock_session = AsyncMock()
        mock_session.call_tool.return_value = mock_call_result
        
        mock_process_manager = AsyncMock(spec=MCPProcessManager)
        mock_process_manager.get_session.return_value = mock_session
        
        bridge = MCPBridge(config_manager, mock_process_manager)
        
        with pytest.raises(RuntimeError) as exc_info:
            await bridge.call_tool("demo", "test_tool", {"param": "val"})
            
        assert "Etwas ging schief!" in str(exc_info.value)



@pytest.mark.asyncio
async def test_mcp_executor_success():
    """Tests if MCPExecutor executes successfully, formats output, and applies hygiene."""
    from elemm_gateway.services.executors import MCPExecutor
    import json
    
    mock_bridge = AsyncMock()
    # Return stringified list of items
    mock_bridge.call_tool.return_value = json.dumps([
        {"id": 1, "name": "Alice", "role": "admin"},
        {"id": 2, "name": "Bob", "role": "user"}
    ])
    
    executor = MCPExecutor(mock_bridge)
    
    tool_data = {
        "id": "mcp:demo:get_users",
        "meta": {
            "server_id": "demo",
            "tool_name": "get_users"
        }
    }
    
    # Run with select hygiene param
    arguments = {
        "_select": "name"
    }
    
    res = await executor.execute(tool_data, arguments)
    res_data = json.loads(res)
    
    # Should only contain names
    assert len(res_data) == 2
    assert res_data[0] == {"name": "Alice"}
    assert res_data[1] == {"name": "Bob"}
    mock_bridge.call_tool.assert_called_once_with("demo", "get_users", {})


@pytest.mark.asyncio
async def test_mcp_executor_error_with_remedy():
    """Tests if MCPExecutor intercepts failures and injects remedies."""
    from elemm_gateway.services.executors import MCPExecutor
    import json
    
    mock_bridge = AsyncMock()
    mock_bridge.call_tool.side_effect = Exception("Rate limit exceeded for GitHub API.")
    
    executor = MCPExecutor(mock_bridge)
    
    tool_data = {
        "id": "mcp:demo:search_repos",
        "remedy": "Bitte reduziere die Anzahl der Anfragen.",
        "meta": {
            "server_id": "demo",
            "tool_name": "search_repos"
        }
    }
    
    res = await executor.execute(tool_data, {})
    res_data = json.loads(res)
    
    assert res_data["status"] == "error"
    assert res_data["_PROTOCOL_ERROR"] == "RATE_LIMIT_EXCEEDED"
    assert "Bitte reduziere die Anzahl der Anfragen." in res_data["remedy"]


@pytest.mark.asyncio
async def test_mcp_executor_heuristic_remedy():
    """Tests if MCPExecutor generates correct intelligent heuristic remedies based on the error content."""
    from elemm_gateway.services.executors import MCPExecutor
    import json
    
    # 1. No custom remedy configured (should return empty remedy)
    mock_bridge = AsyncMock()
    mock_bridge.call_tool.side_effect = Exception("path.block_id should be a valid uuid, instead was undefined")
    executor = MCPExecutor(mock_bridge)
    
    tool_data = {
        "id": "mcp:demo:test_tool",
        "meta": {"server_id": "demo", "tool_name": "test_tool"}
    }
    
    res = await executor.execute(tool_data, {})
    res_data = json.loads(res)
    assert res_data["status"] == "error"
    assert "remedy" not in res_data

    # 2. Configured custom remedy
    tool_data_with_remedy = {
        "id": "mcp:demo:test_tool",
        "meta": {"server_id": "demo", "tool_name": "test_tool"},
        "remedy": "Ensure block_id is a valid Notion UUID. Use notion:search first."
    }
    mock_bridge.call_tool.side_effect = Exception("path.block_id failed validation")
    res = await executor.execute(tool_data_with_remedy, {})
    res_data = json.loads(res)
    assert res_data["status"] == "error"
    assert res_data["remedy"] == "Ensure block_id is a valid Notion UUID. Use notion:search first."

    # 3. Configured custom remedy inside structured JSON error
    json_error_str = '{"status": 400, "object": "error", "code": "validation_error", "message": "path.block_id failed validation"}'
    mock_bridge.call_tool.side_effect = Exception(json_error_str)
    res = await executor.execute(tool_data_with_remedy, {})
    res_data = json.loads(res)
    assert res_data["status"] == 400 or res_data["status"] == "error"
    assert res_data["code"] == "validation_error"
    assert res_data["message"] == "path.block_id failed validation"
    assert res_data["remedy"] == "Ensure block_id is a valid Notion UUID. Use notion:search first."


@pytest.mark.asyncio
async def test_elemm_gateway_mcp_integration():
    """Integration test to verify that ElemmGateway correctly delegates and processes MCP tool execution and discovery."""
    from elemm_gateway.server import ElemmGateway
    import json
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = os.path.join(tmp_dir, "mcp_servers.yaml")
        config_data = {
            "version": "1.0",
            "servers": {
                "demo": {
                    "name": "Demo Server",
                    "transport": "stdio",
                    "command": "python3",
                    "args": []
                }
            }
        }
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config_data, f)
            
        original_expanduser = os.path.expanduser
        with patch("os.path.expanduser", side_effect=lambda x: config_path if "mcp_servers.yaml" in x else original_expanduser(x)):
            gateway = ElemmGateway()
            
            # Mock the discover_landmarks and call_tool of self.mcp_bridge
            from elemm.core.models import Landmark
            mock_landmark = Landmark(
                id="mcp:demo:test_action",
                type="action",
                description="Test Action",
                meta={"server_id": "demo", "tool_name": "test_action"}
            )
            gateway.mcp_bridge.discover_landmarks = AsyncMock(return_value=[mock_landmark])
            gateway.mcp_bridge.call_tool = AsyncMock(return_value="executed_successfully")
            
            # 1. Test direct execution of external MCP tool starting with mcp:
            exec_res = await gateway._execute_single("mcp:demo:test_action", {"arg": "value"})
            assert exec_res == "executed_successfully"
            gateway.mcp_bridge.call_tool.assert_called_once_with("demo", "test_action", {"arg": "value"})
            
            # 2. Test injection: LEVEL A - GLOBAL Mode (default/fallback behavior)
            gateway.config_manager.config["mcp_injection_mode"] = "global"
            site_data = {
                "type": "openapi",
                "landmarks": []
            }
            await gateway._inject_mcp_landmarks(site_data)
            landmark_ids = [getattr(lm, "id") for lm in site_data["landmarks"]]
            assert "mcp:demo" in landmark_ids
            assert "mcp:demo:test_action" in landmark_ids

            # 3. Test injection: LEVEL B - LOCAL Mode (strict separation)
            gateway.config_manager.config["mcp_injection_mode"] = "local"
            
            # External site should NOT receive MCP tools in local mode
            site_data_ext = {
                "type": "openapi",
                "url": "https://api.example.com",
                "landmarks": []
            }
            await gateway._inject_mcp_landmarks(site_data_ext)
            assert not site_data_ext["landmarks"]
            
            # Virtual local connection SHOULD receive MCP tools in local mode
            site_data_local = {
                "type": "native",
                "url": "mcp://local",
                "landmarks": []
            }
            await gateway._inject_mcp_landmarks(site_data_local)
            landmark_ids_local = [getattr(lm, "id") for lm in site_data_local["landmarks"]]
            assert "mcp:demo" in landmark_ids_local
            assert "mcp:demo:test_action" in landmark_ids_local

            # 4. Test injection: LEVEL C - SELECTED Mode (granular)
            gateway.config_manager.config["mcp_injection_mode"] = "selected"
            gateway.config_manager.config["injected_mcp_servers"] = []
            gateway.config_manager.config["injected_mcp_tools"] = ["mcp:demo:test_action"]
            
            site_data_sel = {
                "type": "openapi",
                "url": "https://api.example.com",
                "landmarks": []
            }
            await gateway._inject_mcp_landmarks(site_data_sel)
            landmark_ids_sel = [getattr(lm, "id") for lm in site_data_sel["landmarks"]]
            assert "mcp:demo" in landmark_ids_sel
            assert "mcp:demo:test_action" in landmark_ids_sel

            # If tool is not selected and server is not selected, should NOT inject
            gateway.config_manager.config["injected_mcp_tools"] = []
            site_data_empty = {
                "type": "openapi",
                "url": "https://api.example.com",
                "landmarks": []
            }
            await gateway._inject_mcp_landmarks(site_data_empty)
            assert not site_data_empty["landmarks"]

