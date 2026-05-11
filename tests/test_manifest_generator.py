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
from elemm_gateway.components import ManifestBuilder

def test_manifest_builder_structure():
    """Tests if the central ManifestBuilder generates all required sections."""
    header = ManifestBuilder.build_header("Test API", "1.2.3")
    
    assert "# ELEMM v2 INTERFACE: Test API (v1.2.3)" in header
    assert "### CRITICAL PROTOCOL RULES" in header
    assert "### SESSION GOVERNANCE AND MEMORY" in header
    assert "### GATEWAY GLOBALS" in header
    assert "$step0.items[0].id" in header # Check for the improved piping explanation

def test_manifest_no_double_injection():
    """Tests if inject_globals is idempotent (no double injection)."""
    base_manifest = "### LANDMARK TOPOLOGY\n- **LandmarkA**: Description"
    
    # 1. First injection
    injected = ManifestBuilder.inject_globals(base_manifest)
    assert injected.count("GATEWAY GLOBALS") == 1
    
    # 2. Second injection attempt
    re_injected = ManifestBuilder.inject_globals(injected)
    assert re_injected.count("GATEWAY GLOBALS") == 1
    assert re_injected == injected

def test_legacy_hint_cleanup():
    """Tests if legacy hints like 'inspect_landmarks' are updated."""
    legacy = "Use 'inspect_landmarks' to see details or inspect_landmark(id)."
    cleaned = ManifestBuilder.inject_globals(legacy)
    
    assert "'inspect_landmarks'" not in cleaned
    assert "elemm:inspect_landmark" in cleaned
    assert "inspect_landmark(id)" not in cleaned
