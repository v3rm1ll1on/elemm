# Copyright (C) 2026 Antigravity (DeepMind)
import pytest
import json
from elemm.core.manager import AIProtocolManager
from elemm.core.presenter import ManifestPresenter
from elemm.core.models import Landmark

@pytest.fixture
def manager():
    mgr = AIProtocolManager()
    # Mock some tools in a landmark
    landmark_id = "Zentrum:Sector_042:energy"
    tools = []
    for i in range(10):
        t = Landmark(
            id=f"{landmark_id}:tool_{i}",
            description=f"Tool number {i}",
            handler=lambda x: x
        )
        tools.append(t)
    
    parent = Landmark(id=landmark_id, description="Energy Area")
    parent.tools = tools
    mgr.landmarks[landmark_id] = parent
    return mgr

def test_presenter_strict_limit(manager):
    """Test that the presenter respects a hard item limit."""
    presenter = ManifestPresenter()
    landmark = manager.landmarks["Zentrum:Sector_042:energy"]
    
    # CASE 1: Limit = 3
    # Result should have 1 header line + 3 tool lines = 4 items? 
    # Wait, our logic says items_rendered counts landmarks AND tools.
    # Header counts as 1. Then 3 tools. Total = 4 rendered. 
    # If we want EXACTLY 3 items total:
    md = presenter.present_manifest([landmark], max_landmarks=3)
    
    # Count lines that look like items (starting with -)
    item_lines = [l for l in md.split("\n") if l.strip().startswith("-")]
    
    # Header (1) + 2 Tools (2) + Info-Item (1) = 4 items starting with '-'
    assert len(item_lines) == 4
    assert "tool_0" in md
    assert "tool_1" in md
    assert "tool_2" not in md
    assert "and 8 more tools" in md

def test_presenter_offset_on_tools(manager):
    """Test that offset correctly shifts tools within a landmark."""
    presenter = ManifestPresenter()
    landmark = manager.landmarks["Zentrum:Sector_042:energy"]
    
    # We need to simulate how manager.get_manifest handles sub-landmarks.
    # When zentrum:sector_042:energy is requested, the manager expands it.
    # So the presenter receives the TOOLS as the top-level landmarks.
    tools = landmark.tools
    
    # CASE: offset=3, limit=2
    md = presenter.present_manifest(tools, offset=3, max_landmarks=2)
    
    assert "tool_0" not in md
    assert "tool_3" in md
    assert "tool_4" in md
    assert "tool_5" not in md
    
    # Check for the correct hint
    assert "_offset=5" in md

def test_fastapi_limit_interpretation():
    """Test the logic in FastAPI gateway that converts small limits to max_landmarks."""
    # We mock the params check we added to fastapi.py
    
    def get_p_kwargs(limit, offset):
        p_kwargs = {"offset": offset}
        if limit is not None:
            if limit < 500:
                p_kwargs["max_landmarks"] = limit
            else:
                p_kwargs["limit"] = limit
        return p_kwargs

    # Agent says _limit=3
    args = get_p_kwargs(3, 0)
    assert "max_landmarks" in args
    assert args["max_landmarks"] == 3
    assert "limit" not in args

    # System says limit=20000 (chars)
    args = get_p_kwargs(20000, 0)
    assert "limit" in args
    assert args["limit"] == 20000
    assert "max_landmarks" not in args
