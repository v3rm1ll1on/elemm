# Copyright (C) 2026 Antigravity (DeepMind)
import pytest
import json
import asyncio
import httpx
from elemm_gateway.server import ElemmGateway
from elemm_gateway.services.hygiene import ResponseSquisher

@pytest.fixture
def gateway():
    return ElemmGateway()

def test_response_squisher_list_pagination():
    """Test virtual pagination on lists."""
    data = [{"id": i} for i in range(100)]
    
    # Page 1
    res, truncated, total = ResponseSquisher.squish(data, limit=10, offset=0)
    assert len(res) == 10
    assert res[0]["id"] == 0
    assert res[9]["id"] == 9
    assert truncated is True
    assert total == 100
    
    # Page 2
    res, truncated, total = ResponseSquisher.squish(data, limit=10, offset=10)
    assert len(res) == 10
    assert res[0]["id"] == 10
    assert res[9]["id"] == 19
    assert truncated is True

def test_response_squisher_string_pagination():
    """Test virtual pagination on large strings (logs)."""
    data = "LINE1\nLINE2\nLINE3\nLINE4\nLINE5"
    
    # First 10 chars
    res, truncated, total = ResponseSquisher.squish(data, limit=10, offset=0)
    assert res == "LINE1\nLINE" # 10 chars exactly
    assert truncated is True
    assert total == len(data)
    
    # Next 10 chars
    res, truncated, total = ResponseSquisher.squish(data, limit=10, offset=10)
    assert res == "2\nLINE3\nLI"
    assert truncated is True

def test_smart_truncate_preserves_valid_json():
    """Ensure smart truncation keeps objects parseable and reports truncation."""
    data = {
        "status": "success",
        "giant_list": [{"id": i} for i in range(1000)],
        "giant_string": "A" * 50000
    }
    
    # Apply smart truncation with aggressive limits for testing
    truncated, was_trunc = ResponseSquisher.smart_truncate(data, max_list_items=5, max_string_length=100)
    
    # Verify structure
    assert was_trunc is True
    assert truncated["status"] == "success"
    assert len(truncated["giant_list"]) == 6 # 5 items + info object
    assert "_elemm_info" in truncated["giant_list"][-1]
    assert len(truncated["giant_string"]) < 500
    assert "[TRUNCATED:" in truncated["giant_string"]
    
    # Verify JSON validity
    json_str = json.dumps(truncated)
    parsed = json.loads(json_str)
    assert parsed["status"] == "success"

@pytest.mark.asyncio
async def test_gateway_remedy_injection_native(gateway, monkeypatch):
    """Test that the gateway injects a remedy when native results are truncated."""
    from unittest.mock import AsyncMock, MagicMock
    
    large_data = [{"item": i} for i in range(50)]
    
    # Mock Response
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = large_data
    
    # Mock Client
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_resp)
    
    # Patch the class itself
    monkeypatch.setattr("httpx.AsyncClient", MagicMock(return_value=mock_client))
    
    gateway.active_site_url = "http://mock-site"
    gateway.manifest_loaded = True 
    
    # Call with _limit=5
    res_str = await gateway._execute_single("test_tool", {"_limit": 5})
    res = json.loads(res_str)
    
    assert res["status"] == "success"
    assert len(res["data"]) == 5
    assert "_HYGIENE_NOTICE" in res
    assert "remedy" in res
    assert "_offset=5" in res["remedy"]

@pytest.mark.asyncio
async def test_virtual_pagination_with_offset(gateway, monkeypatch):
    """Test that _offset correctly slices results in the gateway."""
    from unittest.mock import AsyncMock, MagicMock
    
    large_data = [{"id": i} for i in range(50)]
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = large_data
    
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_resp)
    
    monkeypatch.setattr("httpx.AsyncClient", MagicMock(return_value=mock_client))
    
    gateway.active_site_url = "http://mock-site"
    gateway.manifest_loaded = True 
    
    # Call with _limit=5 and _offset=10
    res_str = await gateway._execute_single("test_tool", {"_limit": 5, "_offset": 10})
    res = json.loads(res_str)
    
    assert res["status"] == "success"
    assert len(res["data"]) == 5
    assert res["data"][0]["id"] == 10
    assert res["data"][4]["id"] == 14

@pytest.mark.asyncio
async def test_sequencer_reports_truncation(gateway, monkeypatch):
    """Test that execute_sequence correctly reports _truncated: true when smart_truncate triggers."""
    from elemm_gateway.services.sequencer import SequenceEngine
    from unittest.mock import AsyncMock, MagicMock
    
    # Mock sequence engine with gateway
    engine = SequenceEngine(gateway)
    
    # Mock a tool that returns a giant list
    giant_data = [{"id": i} for i in range(100)]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = giant_data
    
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_resp)
    
    monkeypatch.setattr("httpx.AsyncClient", MagicMock(return_value=mock_client))
    gateway.active_site_url = "http://mock-site"
    gateway.manifest_loaded = True
    gateway.limit_standard = 5000 # Small limit for testing
    
    # Execute a simple 1-step sequence
    actions = [{"action": "city:get_big_data", "alias": "big"}]
    mcp_results = await engine.execute(actions)
    
    # Parse the JSON from the TextContent
    full_json = json.loads(mcp_results[0].text)
    step_res = full_json[0]
    
    # Verify the step result
    assert step_res["_truncated"] is True
    
    # Check if the result contains the truncation info
    res_content = step_res["result"]
    if isinstance(res_content, str):
        assert "_elemm_info" in res_content
    else:
        assert "_elemm_info" in res_content[-1]

def test_response_squisher_nested_list_merging():
    """Verify that multiple nested selections on list items are merged correctly without overwriting."""
    data = {
        "countries": [
            {"id": "AD", "name": "Andorra", "population": 77000},
            {"id": "AL", "name": "Albania", "population": 2800000}
        ]
    }
    
    # Selecting multiple nested list fields
    res, truncated, total = ResponseSquisher.squish(data, select="countries.name,countries.id")
    
    assert "countries" in res
    assert len(res["countries"]) == 2
    assert res["countries"][0] == {"id": "AD", "name": "Andorra"}
    assert res["countries"][1] == {"id": "AL", "name": "Albania"}

def test_response_squisher_space_separated():
    """Verify that space-separated _select strings (common in GraphQL agents) are supported."""
    data = {
        "id": "DE",
        "name": "Germany",
        "capital": "Berlin",
        "currency": "EUR"
    }
    
    # Space-separated
    res, truncated, total = ResponseSquisher.squish(data, select="name capital currency")
    assert res == {"name": "Germany", "capital": "Berlin", "currency": "EUR"}

def test_response_squisher_gql_selection_parsing():
    """Verify that nested GraphQL curly braces syntax is parsed and squished correctly."""
    data = {
        "id": 1,
        "name": "Rick",
        "status": "Alive",
        "origin": {
            "name": "Earth",
            "url": "https://earth.url"
        }
    }
    
    # GraphQL braces nested selection
    res, truncated, total = ResponseSquisher.squish(data, select="id name origin { name }")
    assert res == {
        "id": 1,
        "name": "Rick",
        "origin": {
            "name": "Earth"
        }
    }


@pytest.mark.asyncio
async def test_elemm_help_onboarding_interception(gateway):
    """Verify that calling _elemm-help or _elemm_help directly returns the onboarding help JSON structure."""
    res_str = await gateway._execute_single("_elemm-help", {})
    res = json.loads(res_str)
    
    assert res["status"] == "success"
    assert "onboarding" in res
    assert "Quick Examples" in res["onboarding"]
    assert "Discovery & Navigation" in res["onboarding"]
    assert "1. Search Landmarks & Tools" in res["onboarding"]["Discovery & Navigation"]
    assert "2. Inspect Specific Landmark" in res["onboarding"]["Discovery & Navigation"]
    assert "When to use call_action vs execute_sequence" in res["onboarding"]
    
    # Check that '_elemm_help' alias works exactly the same
    res_str2 = await gateway._execute_single("_elemm_help", {})
    res2 = json.loads(res_str2)
    assert res2["status"] == "success"
    assert "onboarding" in res2
    assert "Discovery & Navigation" in res2["onboarding"]




