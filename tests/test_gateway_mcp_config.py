# Copyright (C) 2026 Marc Stöcker
# Website: https://elemm.dev
#
# This program is licensed under the Business Source License 1.1 (BSL 1.1).
# See the LICENSE file in the root directory for details.

import os
import yaml
import tempfile
import time
from unittest.mock import patch
from elemm_gateway.services.mcp_config import MCPConfigManager

def test_mcp_config_manager_creation():
    """Tests if MCPConfigManager creates default mcp_servers.yaml if missing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = os.path.join(tmp_dir, "mcp_servers.yaml")
        manager = MCPConfigManager(config_path)
        
        assert os.path.exists(config_path)
        servers = manager.get_servers()
        assert "github" in servers
        assert servers["github"]["transport"] == "stdio"
        assert servers["github"]["command"] == "npx"

def test_mcp_config_manager_loading():
    """Tests if MCPConfigManager loads existing valid yaml file."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = os.path.join(tmp_dir, "mcp_servers.yaml")
        custom_config = {
            "version": "1.0",
            "servers": {
                "postgres": {
                    "name": "Postgres Server",
                    "transport": "stdio",
                    "command": "docker",
                    "args": ["run", "postgres"]
                }
            }
        }
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(custom_config, f)
            
        manager = MCPConfigManager(config_path)
        servers = manager.get_servers()
        assert "postgres" in servers
        assert "github" not in servers
        assert servers["postgres"]["command"] == "docker"

def test_mcp_config_env_resolution():
    """Tests if env variables are resolved correctly."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = os.path.join(tmp_dir, "mcp_servers.yaml")
        custom_config = {
            "version": "1.0",
            "servers": {
                "github": {
                    "env": {
                        "TOKEN": "env:MY_TEST_TOKEN",
                        "STATIC": "hello"
                    }
                }
            }
        }
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(custom_config, f)
            
        manager = MCPConfigManager(config_path)
        
        with patch.dict(os.environ, {"MY_TEST_TOKEN": "secret123"}):
            resolved = manager.get_resolved_env("github")
            assert resolved["TOKEN"] == "secret123"
            assert resolved["STATIC"] == "hello"

def test_mcp_config_manager_hot_reload():
    """Tests if config changes are detected and reloaded on reload_if_changed."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = os.path.join(tmp_dir, "mcp_servers.yaml")
        custom_config = {
            "version": "1.0",
            "servers": {
                "server_a": {
                    "name": "Server A"
                }
            }
        }
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(custom_config, f)
            
        manager = MCPConfigManager(config_path)
        assert "server_a" in manager.get_servers()
        assert "server_b" not in manager.get_servers()
        
        # Modify the file on disk
        updated_config = {
            "version": "1.0",
            "servers": {
                "server_b": {
                    "name": "Server B"
                }
            }
        }
        
        # Sleep briefly to ensure the mtime changes
        time.sleep(0.01)
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(updated_config, f)
            
        # Call hot reload
        reloaded = manager.reload_if_changed()
        assert reloaded is True
        assert "server_b" in manager.get_servers()
        assert "server_a" not in manager.get_servers()