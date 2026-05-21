# Copyright (C) 2026 Marc Stöcker
# Website: https://elemm.dev
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

import os
import re
import yaml
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("elemm-gateway")

class MCPConfigManager:
    """
    Handles loading, parsing, and hot-reloading of external MCP server configurations
    from ~/.elemm/mcp_servers.yaml, including environment variable interpolation.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        if not config_path:
            config_path = os.path.expanduser("~/.elemm/mcp_servers.yaml")
        self.config_path = config_path
        self.last_mtime = 0
        self.config: Dict[str, Any] = {"version": "1.0", "servers": {}}
        self.load()

    def load(self) -> Dict[str, Any]:
        """Loads and parses the mcp_servers.yaml file, with sensible defaults if missing."""
        defaults = {
            "version": "1.0",
            "servers": {
                "github": {
                    "name": "GitHub MCP Server",
                    "description": "Ermöglicht das Suchen von Repositories, Erstellen von Issues und Verwalten von PRs.",
                    "transport": "stdio",
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"],
                    "env": {
                        "GITHUB_PERSONAL_ACCESS_TOKEN": "env:GITHUB_PAT"
                    },
                    "instructions": "Verwende diese Tools zur Interaktion mit GitHub. Schone Rate-Limits.",
                    "remedies": {
                        "search_repositories": {
                            "on_error": "Die GitHub-Suche war erfolglos. Prüfe, ob du Sonderzeichen im Query-Parameter verwendet hast, und vereinfache den Suchbegriff."
                        }
                    }
                }
            }
        }

        config_dir = os.path.dirname(self.config_path)
        if config_dir and not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)

        if not os.path.exists(self.config_path):
            try:
                with open(self.config_path, "w", encoding="utf-8") as f:
                    yaml.safe_dump(defaults, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
                self.last_mtime = os.path.getmtime(self.config_path)
                logger.info(f"MCPConfig: Created default configuration at {self.config_path}")
            except Exception as e:
                logger.warning(f"MCPConfig: Could not create default config: {e}")
            self.config = defaults
            return self.config

        try:
            self.last_mtime = os.path.getmtime(self.config_path)
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if not isinstance(data, dict):
                    data = {}
                # Verify basic structure
                if "servers" not in data or not isinstance(data["servers"], dict):
                    data["servers"] = {}
                if "version" not in data:
                    data["version"] = "1.0"
                
                self.config = data
                return self.config
        except Exception as e:
            logger.error(f"MCPConfig: Failed to load from {self.config_path}: {e}")
            self.config = defaults
            return self.config

    def reload_if_changed(self) -> bool:
        """Reloads the configuration if the file has been modified on disk."""
        if not os.path.exists(self.config_path):
            return False
            
        try:
            current_mtime = os.path.getmtime(self.config_path)
            if current_mtime != self.last_mtime:
                logger.info("MCPConfig: File change detected, reloading...")
                self.load()
                return True
        except Exception as e:
            logger.debug(f"MCPConfig: Periodic mtime check failed: {e}")
        return False

    def get_servers(self) -> Dict[str, Dict[str, Any]]:
        """Returns the dictionary of configured external MCP servers."""
        return self.config.get("servers", {})

    def get_server(self, server_id: str) -> Optional[Dict[str, Any]]:
        """Returns the configuration for a specific server."""
        return self.get_servers().get(server_id)

    @classmethod
    def resolve_value(cls, val: Any, vault_manager: Optional[Any] = None) -> Any:
        """Recursively interpolates env variables and vault keys in config values (e.g. 'env:GITHUB_PAT', 'vault:github.com')."""
        if isinstance(val, str):
            if val.startswith("env:"):
                env_var = val[4:]
                return os.environ.get(env_var, "")
            elif val.startswith("vault:"):
                vault_key = val[6:]
                if not vault_manager:
                    vault_path = os.path.expanduser("~/.elemm/vault.json")
                    try:
                        from elemm_gateway.services.vault import VaultManager
                        vault_manager = VaultManager(vault_path)
                    except Exception:
                        pass
                
                if vault_manager:
                    entry = vault_manager.get_entry(vault_key)
                    if entry is not None:
                        if isinstance(entry, str):
                            return entry
                        elif isinstance(entry, dict):
                            return entry.get("value", "")
                return ""
            return val
        elif isinstance(val, dict):
            return {k: cls.resolve_value(v, vault_manager) for k, v in val.items()}
        elif isinstance(val, list):
            return [cls.resolve_value(item, vault_manager) for item in val]
        return val

    def get_resolved_env(self, server_id: str, vault_manager: Optional[Any] = None) -> Dict[str, str]:
        """Returns the fully interpolated environment variable dictionary for a server."""
        server_conf = self.get_server(server_id)
        if not server_conf or "env" not in server_conf:
            return {}
        
        raw_env = server_conf["env"]
        if not isinstance(raw_env, dict):
            return {}
            
        resolved = {}
        for k, v in raw_env.items():
            resolved[str(k)] = str(self.resolve_value(v, vault_manager))
        return resolved
