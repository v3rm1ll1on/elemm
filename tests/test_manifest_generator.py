# Copyright (C) 2026 Marc Stöcker
# Website: https://elemm.dev
#
# This program is licensed under the Business Source License 1.1 (BSL 1.1).
# See the LICENSE file in the root directory for details.

import pytest
from elemm_gateway.components import ManifestBuilder

def test_manifest_builder_structure():
    """Tests if the central ManifestBuilder generates all required sections."""
    header = ManifestBuilder.build_header("Test API", "1.2.3")
    
    assert "# ELEMM v2 INTERFACE: Test API (v1.2.3)" in header
    assert "### OPERATIONAL HYGIENE" in header
    assert "### SESSION GOVERNANCE" in header
    assert "list_aliases" in header
    assert "HYGIENE" in header # Check for the new operational hygiene rule
    assert "$step0.id" in header

def test_manifest_no_double_injection():
    """Tests if inject_globals is idempotent (no double injection)."""
    base_manifest = "### LANDMARK TOPOLOGY\n- **LandmarkA**: Description"
    
    # 1. First injection
    injected = ManifestBuilder.inject_globals(base_manifest)
    assert "PROTOCOL WORKFLOW" in injected
    
    # 2. Second injection attempt
    re_injected = ManifestBuilder.inject_globals(injected)
    assert re_injected.count("PROTOCOL WORKFLOW") == 1
    assert re_injected == injected

def test_legacy_hint_cleanup():
    """Tests if legacy hints like 'inspect_landmarks' are updated."""
    legacy = "Use 'inspect_landmarks' to see details or inspect_landmark(id)."
    cleaned = ManifestBuilder.inject_globals(legacy)
    
    assert "'inspect_landmarks'" not in cleaned
    assert "'inspect_landmark'" in cleaned
    assert "inspect_landmark(id)" not in cleaned