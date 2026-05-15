# Copyright (C) 2026 Marc Stöcker
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
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("elemm-gateway")

class VaultManager:
    """Handles API key management and injection."""
    def __init__(self, vault_path: str):
        self.vault_path = vault_path
        self.vault = self.load()

    def load(self) -> Dict[str, Any]:
        if not os.path.exists(self.vault_path):
            return {}
        try:
            with open(self.vault_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Vault: Failed to load from {self.vault_path}: {e}")
            return {}

    def get_entry(self, host: str) -> Optional[Dict[str, Any]]:
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
        headers = {}
        self.apply_auth(host, {}, headers)
        return headers

    def get_auth_param_names(self, host: str) -> List[str]:
        """Returns names of parameters that this vault can provide for the host."""
        entry = self.get_entry(host)
        if not entry: return []
        if isinstance(entry, str): return ["key"]
        name = entry.get("name", "key")
        return [name]
