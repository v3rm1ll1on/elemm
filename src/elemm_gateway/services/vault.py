# Copyright (C) 2026 Marc Stöcker
# Website: https://elemm.dev
#
# This program is licensed under the Business Source License 1.1 (BSL 1.1).
# See the LICENSE file in the root directory for details.

import os
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("elemm-gateway")

class VaultManager:
    """Handles API key management and injection."""
    DEFAULT_USER_AGENT = "ElemmGateway/1.0 (Autonomous Agent)"
    user_agent: str = DEFAULT_USER_AGENT

    def __init__(self, vault_path: str, user_agent: Optional[str] = None):
        self.vault_path = vault_path
        self.last_mtime = 0
        self.vault = {}
        self.load()
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT

    def load(self) -> Dict[str, Any]:
        if not os.path.exists(self.vault_path):
            try:
                config_dir = os.path.dirname(self.vault_path)
                if config_dir:
                    os.makedirs(config_dir, exist_ok=True)
                with open(self.vault_path, "w") as f:
                    json.dump({}, f, indent=2)
                self.last_mtime = os.path.getmtime(self.vault_path)
                logger.info(f"Vault: Created default empty vault at {self.vault_path}")
            except Exception as e:
                logger.warning(f"Vault: Could not create default empty vault: {e}")
            self.vault = {}
            return {}
        try:
            self.last_mtime = os.path.getmtime(self.vault_path)
            with open(self.vault_path, "r") as f:
                self.vault = json.load(f)
                return self.vault
        except Exception as e:
            logger.error(f"Vault: Failed to load from {self.vault_path}: {e}")
            self.vault = {}
            return {}

    def reload_if_changed(self) -> bool:
        """Reloads the vault if the file has been modified on disk."""
        if not os.path.exists(self.vault_path):
            return False
        try:
            current_mtime = os.path.getmtime(self.vault_path)
            if current_mtime != self.last_mtime:
                logger.info("Vault: File change detected, reloading...")
                self.load()
                return True
        except Exception as e:
            logger.debug(f"Vault: Periodic mtime check failed: {e}")
        return False

    def get_entry(self, host: str) -> Optional[Dict[str, Any]]:
        self.reload_if_changed()
        return self.vault.get(host)

    def apply_auth(self, host: str, params: Dict[str, Any], headers: Dict[str, Any]):
        entry = self.get_entry(host)
        if not entry:
            return False
            
        # Handle simple string entries (legacy/shorthand support)
        if isinstance(entry, str):
            params["key"] = entry
            logger.info(f"Vault: Applied simple apiKey for {host}")
            return True

        if not isinstance(entry, dict):
            logger.warning(f"Vault: Entry for {host} is not a dict or string.")
            return False

        auth_type = entry.get("type", "apiKey")
        name = entry.get("name", "key")
        val = entry.get("value", "")
        
        if auth_type == "apiKey":
            target = entry.get("in", "query")
            if target == "header":
                headers[name] = val
            else:
                params[name] = val
        elif auth_type == "bearer":
            headers["Authorization"] = f"Bearer {val}"
        elif auth_type == "basic":
            headers["Authorization"] = f"Basic {val}"
        
        logger.info(f"Vault: Applied {auth_type} for {host}")
        return True

    def get_headers(self, url: str) -> Dict[str, str]:
        """Returns headers for a given URL/host."""
        from urllib.parse import urlparse
        host = urlparse(url).netloc
        headers = {"User-Agent": self.user_agent}
        self.apply_auth(host, {}, headers)
        return headers

    def get_auth_param_names(self, host: str) -> List[str]:
        """Returns names of parameters that this vault can provide for the host."""
        entry = self.get_entry(host)
        if not entry: return []
        if isinstance(entry, str): return ["key"]
        name = entry.get("name", "key")
        return [name]