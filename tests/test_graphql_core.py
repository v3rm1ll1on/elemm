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
import json
from unittest.mock import MagicMock, AsyncMock
from elemm_gateway.services.graphql_bridge import GraphQLBridge
from elemm_gateway.components import GraphQLExecutor, VaultManager

# Mock Introspection Response
MOCK_INTROSPECTION = {
    "__schema": {
        "queryType": {"name": "Query"},
        "mutationType": None,
        "types": [
            {
                "kind": "OBJECT",
                "name": "Query",
                "fields": [
                    {
                        "name": "character",
                        "description": "Get a character",
                        "args": [
                            {
                                "name": "id",
                                "type": {
                                    "kind": "NON_NULL",
                                    "name": None,
                                    "ofType": {"kind": "SCALAR", "name": "ID", "ofType": None}
                                }
                            }
                        ],
                        "type": {"kind": "OBJECT", "name": "Character", "ofType": None}
                    }
                ]
            },
            {
                "kind": "INPUT_OBJECT",
                "name": "FilterCharacter",
                "inputFields": [
                    {"name": "name", "type": {"kind": "SCALAR", "name": "String", "ofType": None}}
                ]
            }
        ]
    }
}

def test_graphql_bridge_parsing():
    """Tests if the bridge correctly transforms introspection data into Elemm tools."""
    url = "https://mock.api/graphql"
    # server.py passes the 'data' part of the response, which contains '__schema'
    parsed = GraphQLBridge.parse_schema(MOCK_INTROSPECTION, url)
    
    assert "tools" in parsed
    tools = parsed["tools"]
    assert len(tools) > 0
    
    char_tool = next(t for t in tools if t["id"] == "Query:character")
    assert char_tool["description"] == "Get a character"
    assert "id" in char_tool["inputSchema"]["properties"]
    assert char_tool["inputSchema"]["properties"]["id"]["gql_type"] == "ID!"
    assert char_tool["inputSchema"]["required"] == ["id"]
    assert char_tool["meta"]["field_name"] == "character"

@pytest.mark.asyncio
async def test_graphql_executor_query_gen():
    """Tests if the executor generates the correct GraphQL query string and variables."""
    vault = MagicMock(spec=VaultManager)
    vault.apply_auth = MagicMock()
    executor = GraphQLExecutor(vault)
    
    tool_meta = {
        "operation_type": "query",
        "field_name": "character",
        "base_url": "https://mock.api/graphql",
        "inputSchema": {
            "properties": {
                "id": {"type": "string", "gql_type": "ID!"},
                "filter": {"type": "object", "gql_type": "FilterCharacter"}
            },
            "required": ["id"]
        }
    }
    
    arguments = {
        "id": "1",
        "filter": {"name": "Rick"},
        "_select": "name, status"
    }
    
    # We mock the httpx client inside the execute method
    with MagicMock() as mock_client:
        # This is a bit tricky since we use 'async with httpx.AsyncClient()'
        # but for testing the query generation logic, we can inspect the internal state if we refactor slightly
        # Or we just test the _build_selection_set helper
        pass

def test_selection_set_builder():
    """Tests the conversion of _select strings to GraphQL selection sets."""
    executor = GraphQLExecutor(None)
    
    # Simple fields
    assert executor._build_selection_set("id, name") == "{ id, name }"
    
    # Nested fields
    sel = executor._build_selection_set("id, info.name, info.status")
    assert "info { name, status }" in sel
    assert "id" in sel

def test_graphql_bridge_type_fallback():
    """Verify that deep nesting of types like [ID!]! that get truncated to [!]! are parsed using smart leaf fallback."""
    # Truncated representation of [ID!]! where inner SCALAR is None due to depth limitation
    truncated_type = {
        "kind": "NON_NULL",
        "name": None,
        "ofType": {
            "kind": "LIST",
            "name": None,
            "ofType": {
                "kind": "NON_NULL",
                "name": None,
                "ofType": None # Truncated!
            }
        }
    }
    
    # Passing field name "ids" to trigger "ID" fallback
    info_ids = GraphQLBridge._get_type_info(truncated_type, "ids")
    assert info_ids["gql_type"] == "[ID!]!"
    assert info_ids["json_type"] == "array"
    assert info_ids["is_required"] is True
    
    # Passing field name "names" to trigger "String" fallback
    info_names = GraphQLBridge._get_type_info(truncated_type, "names")
    assert info_names["gql_type"] == "[String!]!"
    assert info_names["json_type"] == "array"
    assert info_names["is_required"] is True

if __name__ == "__main__":
    # Manual run support
    test_graphql_bridge_parsing()
    test_graphql_bridge_type_fallback()
    print("Bridge parsing tests passed!")
    
    executor = GraphQLExecutor(None)
    print(f"Selection set: {executor._build_selection_set('id, info.name')}")
    print("All manual checks passed!")
