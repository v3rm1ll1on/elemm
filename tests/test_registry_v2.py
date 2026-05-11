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
from pathlib import Path
import yaml
from elemm.core.registry import MetadataRegistry
from elemm.core.models import Parameter

def test_registry_load_and_get(tmp_path):
    # Erstelle temporäre YAML
    yaml_content = {
        "global_aliases": {
            "city": ["location", "town"]
        },
        "landmarks": [
            {
                "id": "weather",
                "description": "Weather info",
                "tools": [
                    {
                        "id": "get",
                        "description": "Get weather",
                        "parameters": [
                            {"name": "city", "description": "The city", "aliases": ["place"]}
                        ]
                    }
                ]
            }
        ]
    }
    yaml_file = tmp_path / "landmarks.yaml"
    with open(yaml_file, "w") as f:
        yaml.dump(yaml_content, f)

    registry = MetadataRegistry(yaml_file)
    
    # Test Root Landmark
    root = registry.get("weather")
    assert root is not None
    assert root.description == "Weather info"
    
    # Test Tool Landmark (namespaced)
    tool = registry.get("weather:get")
    assert tool is not None
    assert tool.description == "Get weather"
    assert len(tool.parameters) == 1
    assert tool.parameters[0].name == "city"

    # Test Synonyms
    syns = registry.get_synonyms("city", "weather:get")
    assert "location" in syns
    assert "town" in syns
    assert "place" in syns

def test_registry_empty_or_missing():
    registry = MetadataRegistry("non_existent.yaml")
    assert registry.get("any") is None
