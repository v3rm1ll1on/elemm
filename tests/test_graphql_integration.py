import pytest
import respx
import httpx
import json
from elemm_gateway.server import ElemmGateway
from elemm_gateway.graphql_bridge import GraphQLBridge

MOCK_GQL_URL = "https://api.test/graphql"

MOCK_INTRO_DATA = {
    "data": {
        "__schema": {
            "queryType": {"name": "Query"},
            "mutationType": None,
            "types": [
                {
                    "kind": "OBJECT",
                    "name": "Query",
                    "fields": [
                        {"name": "test", "description": "test query", "args": [], "type": {"kind": "SCALAR", "name": "String"}}
                    ]
                }
            ]
        }
    }
}

@pytest.mark.asyncio
@respx.mock
async def test_gateway_graphql_connect():
    """Tests the full connection flow for a GraphQL API using mocks."""
    gateway = ElemmGateway("test-gateway")
    
    # Mock the introspection call
    respx.post(MOCK_GQL_URL).mock(return_value=httpx.Response(200, json=MOCK_INTRO_DATA))
    
    # Execute connect
    results = await gateway._connect(MOCK_GQL_URL)
    
    # Verify results
    assert any("Connected to GraphQL API" in content.text for content in results)
    assert gateway.active_site_url == MOCK_GQL_URL
    assert MOCK_GQL_URL in gateway.connected_sites
    
    site_data = gateway.connected_sites[MOCK_GQL_URL]
    assert site_data["type"] == "graphql"
    assert len(site_data["tools"]) > 0
    assert "Query_test" in [t["name"] for t in site_data["tools"]]
    assert "# 🚀 ELEMM v2 INTERFACE" in site_data["manifest"]

@pytest.mark.asyncio
@respx.mock
async def test_gateway_graphql_execution():
    """Tests the execution of a GraphQL tool call through the gateway."""
    gateway = ElemmGateway("test-gateway")
    
    # 1. Setup connected state
    respx.post(MOCK_GQL_URL).mock(return_value=httpx.Response(200, json=MOCK_INTRO_DATA))
    await gateway._connect(MOCK_GQL_URL)
    
    # 2. Mock the actual tool execution call
    respx.post(MOCK_GQL_URL).mock(return_value=httpx.Response(200, json={"data": {"test": "hello world"}}))
    
    # 3. Call tool
    # Tool name is category_field
    result_contents = await gateway._execute_single("Query_test", {"_select": "test"})
    
    # Verify execution
    assert "hello world" in result_contents
    assert respx.calls.call_count > 1 # One for connect, one for execute
