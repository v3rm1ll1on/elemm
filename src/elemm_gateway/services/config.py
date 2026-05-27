# Copyright (C) 2026 Marc Stöcker
# Website: https://elemm.dev
#
# This program is licensed under the Business Source License 1.1 (BSL 1.1).
# See the LICENSE file in the root directory for details.

import os
import json
import logging
from typing import Any, Dict

logger = logging.getLogger("elemm-gateway")

class ConfigManager:
    """Handles gateway configuration with persistence and sensible defaults."""
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.last_mtime = 0
        self.config = self.load()

    def load(self) -> Dict[str, Any]:
        defaults = {
            "limit_standard": 30000,
            "limit_inspect": 20000,
            "limit_search_items": 10,
            "max_landmarks_per_view": 20,
            "max_tools_per_landmark": 5,
            "timeout_seconds": 30,
            "retry_attempts": 3,
            "retry_delay_ms": 1000,
            "user_agent": "ElemmGateway/1.0 (Autonomous Agent)",
            "mcp_injection_mode": "global",
            "injected_mcp_servers": [],
            "injected_mcp_tools": [],
            "security": {
                "prevent_key_leakage": True,
                "disallowed_patterns": ["delete", "remove", "purge", "destroy"],
                "allowed_methods": ["GET", "POST", "PUT", "PATCH", "DELETE"],
                "disallowed_landmarks": [],
                "disallowed_actions": []
            }
        }
        
        config_dir = os.path.dirname(self.config_path)
        if not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)

        if not os.path.exists(self.config_path):
            try:
                with open(self.config_path, "w") as f:
                    json.dump(defaults, f, indent=2)
                self.last_mtime = os.path.getmtime(self.config_path)
                logger.info(f"Config: Created default configuration at {self.config_path}")
            except Exception as e:
                logger.warning(f"Config: Could not create default config: {e}")
            return defaults
            
        try:
            self.last_mtime = os.path.getmtime(self.config_path)
            with open(self.config_path, "r") as f:
                data = json.load(f)
                # Ensure all default keys are present (migration support)
                updated = False
                for k, v in defaults.items():
                    if k not in data:
                        data[k] = v
                        updated = True
                if updated:
                    with open(self.config_path, "w") as f:
                        json.dump(data, f, indent=2)
                return data
        except Exception as e:
            logger.error(f"Config: Failed to load from {self.config_path}: {e}")
            return defaults

    def reload_if_changed(self) -> bool:
        """Reloads the configuration if the file has been modified."""
        if not os.path.exists(self.config_path):
            return False
            
        try:
            current_mtime = os.path.getmtime(self.config_path)
            if current_mtime != self.last_mtime:
                logger.info("Config: File change detected, reloading...")
                self.config = self.load()
                return True
        except Exception as e:
            logger.debug(f"Config: Periodic mtime check failed: {e}")
        return False

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)