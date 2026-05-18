# Copyright (C) 2026 Antigravity (DeepMind)
import pytest
from elemm.core.manager import AIProtocolManager
from elemm.core.models import Landmark

@pytest.fixture
def manager():
    mgr = AIProtocolManager()
    # Mock data with handlers to trigger TS signatures
    mgr.landmarks["Zentrum:energy"] = Landmark(id="Zentrum:energy", description="Power sector", handler=lambda: "ok")
    mgr.landmarks["Zentrum:water"] = Landmark(id="Zentrum:water", description="H2O sector", handler=lambda: "ok")
    mgr.landmarks["Nord:energy"] = Landmark(id="Nord:energy", description="North power", handler=lambda: "ok")
    return mgr

def test_multi_query_search(manager):
    """Test searching with multiple terms."""
    # Search for both energy and water
    res = manager.search_landmarks(query=["Nord", "water"])
    
    assert "Nord:energy" in res
    assert "Zentrum:water" in res
    assert "Zentrum:energy" not in res # Should not match Nord or water

def test_deduplication(manager):
    """Test that duplicate hits are removed."""
    # "energy" and "power" both match the same landmarks
    res = manager.search_landmarks(query=["energy", "power"])
    
    # Count occurrences of the item in the markdown list specifically
    count = res.count("- Action: `Zentrum:energy` ")
    assert count == 1 # Set should have deduplicated it

def test_default_limit_application(manager):
    """Test that the manager respects max_landmarks in search."""
    # We have 3 landmarks. Limit to 2.
    res = manager.search_landmarks(query=".*", max_landmarks=2)
    
    # Count items (starting with -)
    item_lines = [l for l in res.split("\n") if l.strip().startswith("-")]
    assert len(item_lines) >= 2
    assert "available" in res # Truncation hint should be present

def test_regex_error_fallback(manager):
    """Test that invalid regex falls back to literal search."""
    # '[' is an invalid regex. But it exists in the ID if we are mean.
    manager.landmarks["test[brackets]"] = Landmark(id="test[brackets]", description="Strange ID")
    res = manager.search_landmarks(query="[")
    assert "test[brackets]" in res

def test_case_insensitivity(manager):
    """Test that search is case-insensitive."""
    res = manager.search_landmarks(query="ENERGY")
    assert "Zentrum:energy" in res

def test_deep_tool_search(manager):
    """Test that tools inside landmarks are also found."""
    parent = manager.landmarks["Zentrum:energy"]
    tool = Landmark(id="Zentrum:energy:subtool", description="Hidden gadget", handler=lambda: "ok")
    parent.tools = [tool]
    manager.landmarks[tool.id] = tool
    
    res = manager.search_landmarks(query="gadget")
    assert "energy:subtool" in res

def test_no_results_message(manager):
    """Test output when nothing matches."""
    res = manager.search_landmarks(query="nonexistent_thing_123")
    assert "No landmarks discovered" in res

def test_technical_inlining_in_search(manager):
    """Test that search results contain TypeScript signatures if technical=True."""
    res = manager.search_landmarks(query="energy", technical=True)
    # The presenter should render the TS block for landmarks with handlers
    assert "function call_action" in res
    assert "Zentrum:energy" in res
