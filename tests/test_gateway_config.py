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

import pytest
import os
import json
import tempfile
from unittest.mock import patch
from elemm_gateway.components import ConfigManager
from elemm_gateway.server import ElemmGateway

def test_config_manager_creation():
    """Tests if ConfigManager creates default config if missing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = os.path.join(tmp_dir, "config.json")
        manager = ConfigManager(config_path)
        
        assert os.path.exists(config_path)
        assert manager.get("limit_standard") == 5000
        assert manager.get("limit_inspect") == 20000
        
        with open(config_path, "r") as f:
            data = json.load(f)
            assert data["limit_standard"] == 5000

def test_config_manager_merging():
    """Tests if ConfigManager merges defaults with existing partial config."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = os.path.join(tmp_dir, "config.json")
        os.makedirs(tmp_dir, exist_ok=True)
        # Pre-create partial config
        with open(config_path, "w") as f:
            json.dump({"limit_standard": 9999}, f)
            
        manager = ConfigManager(config_path)
        
        assert manager.get("limit_standard") == 9999
        assert manager.get("limit_inspect") == 20000 # Came from defaults
        assert manager.get("timeout_seconds") == 30 # Came from defaults

def test_gateway_initialization_with_config():
    """Tests if Gateway correctly initializes with config values via ConfigManager."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = os.path.join(tmp_dir, "config.json")
        os.makedirs(tmp_dir, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump({
                "limit_standard": 1234,
                "limit_inspect": 4321
            }, f)
            
        # Patch expanduser to point to our temp config file
        with patch("os.path.expanduser", side_effect=lambda x: config_path if "config.json" in x else x):
            gateway = ElemmGateway()
            assert gateway.limit_standard == 1234
            assert gateway.limit_inspect == 4321
            assert gateway.config_manager.get("timeout_seconds") == 30
