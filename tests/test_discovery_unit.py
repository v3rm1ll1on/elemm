import pytest
from elemm.discovery import map_type, resolve_refs
from typing import List, Optional, Union
from enum import Enum
from pydantic import BaseModel

class MyEnum(str, Enum):
    A = "a"
    B = "b"

def test_map_type_basic():
    assert map_type(str)[0] == "string"
    assert map_type(int)[0] == "integer"
    assert map_type(float)[0] == "number"
    assert map_type(bool)[0] == "boolean"
    assert map_type(list)[0] == "array"

def test_map_type_enum():
    t, options = map_type(MyEnum)
    assert t == "string"
    assert options == ["a", "b"]

def test_map_type_complex():
    assert map_type(Optional[str])[0] == "string"
    assert map_type(List[int])[0] == "array"
    assert map_type(Union[str, int])[0] == "string" # Fallback to first

def test_resolve_refs():
    schema = {
        "properties": {
            "user": {"$ref": "#/$defs/User"}
        },
        "$defs": {
            "User": {
                "type": "object",
                "properties": {"name": {"type": "string"}}
            }
        }
    }
    defs = schema["$defs"]
    resolved = resolve_refs(schema, defs)
    assert resolved["properties"]["user"]["type"] == "object"
    assert resolved["properties"]["user"]["properties"]["name"]["type"] == "string"

def test_map_type_from_dict():
    # Test mapping from a JSON schema dict
    field_info = {"type": "integer", "description": "some int"}
    assert map_type(field_info)[0] == "integer"
    
    enum_info = {"type": "string", "enum": ["x", "y"]}
    assert map_type(enum_info)[1] == ["x", "y"]
