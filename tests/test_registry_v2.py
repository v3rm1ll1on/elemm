# Copyright (C) 2026 Marc Stöcker
# Website: https://elemm.dev
#
# This program is licensed under the Business Source License 1.1 (BSL 1.1).
# See the LICENSE file in the root directory for details.

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