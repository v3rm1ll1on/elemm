# Copyright (C) 2026 Marc Stöcker
# Comprehensive Test suite for the Elemm Gateway Dashboard Backend

import os
import json
import pytest
import time
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket
from fastapi import HTTPException

import elemm_gateway.ui_backend.dashboard_server as dashboard_server

@pytest.fixture(autouse=True)
def mock_dashboard_environment(tmp_path, monkeypatch):
    """
    Sandboxes the dashboard server config and vault files into a temporary directory
    to prevent modifying the user's real settings in ~/.elemm/.
    Also resets the GLOBAL_STATE dictionary before each test run.
    """
    # Create isolated files in the pytest temp directory
    temp_config = tmp_path / "config.json"
    temp_vault = tmp_path / "vault.json"
    
    # Write default test data
    temp_config.write_text(json.dumps({
        "security": {
            "disallowed_patterns": [],
            "disallowed_landmarks": [],
            "allowed_methods": []
        },
        "limit_standard": 30000,
        "limit_inspect": 20000,
        "timeout_seconds": 30,
        "retry_attempts": 3,
        "retry_delay_ms": 1000,
        "ui": {
            "display_mode": "tokens",
            "char_to_token_ratio": 4.0
        }
    }))
    
    temp_vault.write_text(json.dumps({
        "test_host": {
            "type": "apiKey",
            "value": "super-secret-mcp-key-123"
        }
    }))
    
    # Override globals on the target dashboard module
    monkeypatch.setattr(dashboard_server, "CONFIG_PATH", str(temp_config))
    monkeypatch.setattr(dashboard_server, "VAULT_PATH", str(temp_vault))
    
    # Reset in-memory master state to clean defaults
    dashboard_server.GLOBAL_STATE.clear()
    dashboard_server.GLOBAL_STATE.update({
        "active_sites_count": 0,
        "total_tokens": 0,
        "landmark_count": 0,
        "last_action": "Waiting for data...",
        "tokens_in": 0,
        "tokens_out": 0,
        "chars_in": 0,
        "chars_out": 0,
        "version": dashboard_server.__version__,
        "status": "online",
        "sessions": {},
        "manifests": {},
        "history": []
    })
    
    return {
        "config_file": temp_config,
        "vault_file": temp_vault
    }

def test_status_endpoint():
    """Verify that /api/v1/status retrieves the correct, initial Aggregated state."""
    client = TestClient(dashboard_server.app)
    
    response = client.get("/api/v1/status")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["version"] == dashboard_server.__version__
    assert "uptime" in data
    assert data["security_level"] == "standard"
    assert data["active_clients"] == 0

def test_config_endpoints():
    """Verify reading and writing configurations via the HTTP REST API."""
    client = TestClient(dashboard_server.app)
    
    # 1. Read default config
    response = client.get("/api/v1/config")
    assert response.status_code == 200
    assert response.json()["limit_standard"] == 30000
    
    # 2. Write updated config
    updated_config = {
        "security": {
            "disallowed_patterns": ["admin_secret"],
            "disallowed_landmarks": [],
            "allowed_methods": []
        },
        "limit_standard": 150000,
        "limit_inspect": 25000
    }
    response = client.post("/api/v1/config", json=updated_config)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    # 3. Read again to verify persistence
    response = client.get("/api/v1/config")
    assert response.status_code == 200
    data = response.json()
    assert data["limit_standard"] == 150000
    assert "admin_secret" in data["security"]["disallowed_patterns"]

def test_vault_endpoints():
    """Verify reading, writing, and summaries of credentials in the Vault."""
    client = TestClient(dashboard_server.app)
    
    # 1. Read default vault credentials
    response = client.get("/api/v1/vault")
    assert response.status_code == 200
    assert "test_host" in response.json()
    assert response.json()["test_host"]["value"] == "super-secret-mcp-key-123"
    
    # 2. Update vault with new credentials
    new_vault = {
        "secure_gateway": {
            "type": "bearer",
            "token": "bearer-token-abc"
        }
    }
    response = client.post("/api/v1/vault", json=new_vault)
    assert response.status_code == 200
    
    # 3. Verify updated credentials
    response = client.get("/api/v1/vault")
    assert response.status_code == 200
    assert "secure_gateway" in response.json()
    
    # 4. Check UI-friendly vault summary
    response = client.get("/api/v1/vault/summary")
    assert response.status_code == 200
    summary = response.json()
    assert len(summary) == 1
    assert summary[0]["host"] == "secure_gateway"
    assert summary[0]["type"] == "bearer"
    assert summary[0]["status"] == "configured"

def test_publish_activity_and_session_stats():
    """Test telemetry event aggregation via the internal publish endpoint."""
    client = TestClient(dashboard_server.app)
    
    # Define a simulation event
    event = {
        "session_id": "agent-session-42",
        "last_action": "CALL: city:get_security_logs",
        "tokens_in": 120,
        "tokens_out": 380,
        "chars_in": 480,
        "chars_out": 1520,
        "status": "success",
        "timestamp": time.time(),
        "request_id": "ab81d2",
        "input": {"since_timestamp": 1789000},
        "output": "[LOG] Rerouting check completed successfully."
    }
    
    response = client.post("/api/v1/internal/publish", json=event)
    assert response.status_code == 200
    assert response.json()["status"] == "aggregated"
    assert response.json()["session"] == "agent-session-42"
    
    # Check if global counters accumulated correctly
    status_resp = client.get("/api/v1/status")
    status_data = status_resp.json()
    assert status_data["tokens_in"] == 120
    assert status_data["tokens_out"] == 380
    assert status_data["chars_in"] == 480
    assert status_data["chars_out"] == 1520
    
    # Verify session-specific data API
    sessions_resp = client.get("/api/v1/sessions")
    assert sessions_resp.status_code == 200
    sessions = sessions_resp.json()
    assert "agent-session-42" in sessions
    
    session = sessions["agent-session-42"]
    assert session["tokens_in"] == 120
    assert session["chars_out"] == 1520
    
    # Verify correct insertion into history
    assert len(session["history"]) == 1
    history_entry = session["history"][0]
    assert history_entry["action"] == "CALL: city:get_security_logs"
    assert history_entry["input"] == {"since_timestamp": 1789000}
    assert history_entry["output"] == "[LOG] Rerouting check completed successfully."

def test_reset_dashboard_retains_counters():
    """Verify that dashboard resetting clears logs and sessions but keeps global tokens."""
    client = TestClient(dashboard_server.app)
    
    # 1. Publish data
    client.post("/api/v1/internal/publish", json={
        "session_id": "transient-session",
        "tokens_in": 500
    })
    
    # 2. Reset the history
    response = client.post("/api/v1/reset")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    # 3. Verify history is cleared but global accumulator persists
    status_resp = client.get("/api/v1/status")
    status_data = status_resp.json()
    assert status_data["tokens_in"] == 500 # Kept!
    assert status_data["sessions"] == {}   # Wiped!
    assert status_data["history"] == []    # Wiped!

def test_websocket_trace_connection():
    """Test standard WebSocket handshakes and active status push streams."""
    client = TestClient(dashboard_server.app)
    
    with client.websocket_connect("/ws/trace") as websocket:
        # FastAPI server broadcasts current status immediately on connection
        data = websocket.receive_json()
        assert data["type"] == "status_update"
        assert data["status"] == "online"
        assert "uptime" in data
        assert "sessions" in data

def test_session_manifest_endpoint():
    """Test retrieving session-specific manifest files."""
    client = TestClient(dashboard_server.app)
    
    # 1. Non-existent session manifest check
    response = client.get("/api/v1/sessions/non_existent/manifest")
    assert response.status_code == 200
    assert response.json()["manifest"] is None
    
    # 2. Publish manifest in state
    client.post("/api/v1/internal/publish", json={
        "session_id": "session-777",
        "manifest": "### LANDMARK MANIFEST\n- Nord:Sector_1\n"
    })
    
    # 3. Fetch manifest again
    response = client.get("/api/v1/sessions/session-777/manifest")
    assert response.status_code == 200
    assert response.json()["manifest"] == "### LANDMARK MANIFEST\n- Nord:Sector_1\n"

def test_url_extraction_heuristics():
    """Test that publish aggressively extracts the active URL from strings and inputs."""
    client = TestClient(dashboard_server.app)
    
    # Type A: Connection message parsing
    client.post("/api/v1/internal/publish", json={
        "session_id": "session-ext",
        "last_action": "Connected to http://localhost:8000/api"
    })
    sessions = client.get("/api/v1/sessions").json()
    assert sessions["session-ext"]["active_url"] == "http://localhost:8000/api"
    
    # Type B: Input dict parsing
    client.post("/api/v1/internal/publish", json={
        "session_id": "session-ext",
        "input": {"url": "https://api.external.com/graphql"}
    })
    sessions = client.get("/api/v1/sessions").json()
    assert sessions["session-ext"]["active_url"] == "https://api.external.com/graphql"

@pytest.mark.asyncio
async def test_inspect_site_endpoint(monkeypatch):
    """Test inspecting a site by mocking ManifestService.inspect_url."""
    client = TestClient(dashboard_server.app)
    
    # Mock ManifestService.inspect_url
    async def mock_inspect(*args, **kwargs):
        return {
            "status": "success",
            "type": "openapi",
            "manifest": "# Mock OpenAPI Manifest",
            "tools": [
                {"name": "mock_tool_1", "description": "Mocked Endpoint"}
            ]
        }
        
    monkeypatch.setattr(dashboard_server.ManifestService, "inspect_url", mock_inspect)
    
    response = client.get("/api/v1/inspect?url=https://fakeapi.com/swagger.json&session_id=s-inspect")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["type"] == "openapi"
    assert len(data["tools"]) == 1
    
    # Check GLOBAL_STATE manifest and sessions caches
    assert dashboard_server.GLOBAL_STATE["manifests"]["s-inspect"] == "# Mock OpenAPI Manifest"
    sessions = client.get("/api/v1/sessions").json()
    assert "s-inspect" in sessions
    assert sessions["s-inspect"]["active_url"] == "https://fakeapi.com/swagger.json"
    assert sessions["s-inspect"]["tools"][0]["name"] == "mock_tool_1"

def test_inspect_landmark_schema_mapping():
    """Test landmark inspection, mapping inputSchema properties to frontend param arrays."""
    client = TestClient(dashboard_server.app)
    
    # Inject mock session tools with schema specification
    dashboard_server.GLOBAL_STATE["sessions"]["cached-session"] = {
        "active_url": "http://test-server.local",
        "site_type": "graphql",
        "tools": [{
            "name": "mutate_power_flow",
            "description": "Alters grid flow",
            "inputSchema": {
                "required": ["flow_rate"],
                "properties": {
                    "flow_rate": {"type": "integer", "description": "Flow rate in MegaWatts"},
                    "override": {"type": "boolean", "description": "Force layout"}
                }
            }
        }]
    }
    
    response = client.get("/api/v1/inspect/landmark?landmark_id=mutate_power_flow&session_id=cached-session")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["type"] == "graphql"
    
    frontend_data = data["data"]
    assert frontend_data["name"] == "mutate_power_flow"
    assert len(frontend_data["parameters"]) == 2
    
    # Check parameters mappings
    flow_param = next(p for p in frontend_data["parameters"] if p["name"] == "flow_rate")
    assert flow_param["type"] == "integer"
    assert flow_param["required"] is True
    
    override_param = next(p for p in frontend_data["parameters"] if p["name"] == "override")
    assert override_param["type"] == "boolean"
    assert override_param["required"] is False

@pytest.mark.asyncio
async def test_inspect_landmark_fallback_logic(monkeypatch):
    """Test inspect_landmark fallback when cache is cold but URL is provided."""
    client = TestClient(dashboard_server.app)
    
    # Mock fallback service logic
    async def mock_fallback(*args, **kwargs):
        return {
            "status": "success",
            "data": {
                "id": "city:emergency_shutdown",
                "description": "Trigger emergency shutdown protocol",
                "is_tool": True
            }
        }
        
    monkeypatch.setattr(dashboard_server.ManifestService, "inspect_landmark", mock_fallback)
    
    # Populate a barebones session
    dashboard_server.GLOBAL_STATE["sessions"]["fallback-session"] = {
        "active_url": "http://native-city.local",
        "site_type": "native",
        "tools": []
    }
    
    response = client.get("/api/v1/inspect/landmark?landmark_id=city:emergency_shutdown&session_id=fallback-session")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["data"]["id"] == "city:emergency_shutdown"

@pytest.mark.asyncio
async def test_search_landmarks_delegation(monkeypatch):
    """Test search delegation to ManifestService."""
    client = TestClient(dashboard_server.app)
    
    async def mock_search(*args, **kwargs):
        return {
            "status": "success",
            "landmarks": [{"id": "city:traffic"}]
        }
        
    monkeypatch.setattr(dashboard_server.ManifestService, "search_landmarks", mock_search)
    
    # Set search session URL
    dashboard_server.GLOBAL_STATE["sessions"]["search-sess"] = {
        "active_url": "http://search-host.com",
        "site_type": "native"
    }
    
    response = client.get("/api/v1/search?query=traffic&session_id=search-sess")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["landmarks"][0]["id"] == "city:traffic"

@pytest.mark.asyncio
async def test_execute_action_endpoint(monkeypatch):
    """Verify tool action executions across OpenAPI executors."""
    client = TestClient(dashboard_server.app)
    
    # Mock OpenAPIExecutor
    class MockOpenAPIExecutor:
        def __init__(self, *args, **kwargs):
            pass
        async def execute(self, tool_data, parameters):
            return json.dumps({"status": "success", "result": "Action executed via Mock!"})
            
    import elemm_gateway.components as components
    monkeypatch.setattr(components, "OpenAPIExecutor", MockOpenAPIExecutor)
    
    # Setup openapi session tools cache
    dashboard_server.GLOBAL_STATE["sessions"]["exec-session"] = {
        "active_url": "https://api.gateway.local",
        "site_type": "openapi",
        "tools": [{"name": "trigger_remediation", "id": "trigger_remediation"}]
    }
    
    payload = {
        "url": "https://api.gateway.local",
        "action": "trigger_remediation",
        "parameters": {"severity": "critical"},
        "session_id": "exec-session"
    }
    
    response = client.post("/api/v1/execute", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["result"] == "Action executed via Mock!"

def test_config_corrupted_json(monkeypatch, tmp_path):
    """Edge Case: Verify status 500 when config.json contains invalid corrupted JSON."""
    client = TestClient(dashboard_server.app)
    
    temp_config = tmp_path / "corrupted_config.json"
    temp_config.write_text("invalid_json{")
    monkeypatch.setattr(dashboard_server, "CONFIG_PATH", str(temp_config))
    
    response = client.get("/api/v1/config")
    assert response.status_code == 500

def test_vault_corrupted_json(monkeypatch, tmp_path):
    """Edge Case: Verify status 500 when vault.json contains invalid corrupted JSON."""
    client = TestClient(dashboard_server.app)
    
    temp_vault = tmp_path / "corrupted_vault.json"
    temp_vault.write_text("invalid_json{")
    monkeypatch.setattr(dashboard_server, "VAULT_PATH", str(temp_vault))
    
    response = client.get("/api/v1/vault")
    assert response.status_code == 500

def test_vault_summary_corrupted_json_handling(monkeypatch, tmp_path):
    """Edge Case: Verify vault summary handles file corruption gracefully and returns error item."""
    client = TestClient(dashboard_server.app)
    
    temp_vault = tmp_path / "corrupted_vault.json"
    temp_vault.write_text("invalid_json{")
    monkeypatch.setattr(dashboard_server, "VAULT_PATH", str(temp_vault))
    
    response = client.get("/api/v1/vault/summary")
    assert response.status_code == 200
    summary = response.json()
    assert len(summary) == 1
    assert summary[0]["host"] == "Error"
    assert summary[0]["status"] == "error"

def test_session_cleanup_behavior():
    """Edge Case: Verify that sessions older than 24 hours are auto-cleaned on status query."""
    client = TestClient(dashboard_server.app)
    
    now = time.time()
    dashboard_server.GLOBAL_STATE["sessions"] = {
        "fresh-session": {"last_seen": now},
        "expired-session": {"last_seen": now - 90000} # > 24 hours (86400s)
    }
    
    # Query status to trigger the cleanup logic
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    
    # Check session registry
    sessions = dashboard_server.GLOBAL_STATE["sessions"]
    assert "fresh-session" in sessions
    assert "expired-session" not in sessions

def test_inspect_landmark_missing_url_error():
    """Edge Case: Inspecting a landmark with a cold cache and no active URL yields HTTP 400."""
    client = TestClient(dashboard_server.app)
    
    # We query for a landmark in a session that doesn't exist/has no active URL
    response = client.get("/api/v1/inspect/landmark?landmark_id=city:lockdown&session_id=cold-session")
    assert response.status_code == 400
    assert "No active URL found" in response.json()["detail"]

def test_execute_action_incomplete_payload():
    """Edge Case: Executing actions with missing URLs or action parameters yields HTTP 400."""
    client = TestClient(dashboard_server.app)
    
    # Missing action field
    response = client.post("/api/v1/execute", json={"url": "http://api.local"})
    assert response.status_code == 400
    
    # Missing url field
    response = client.post("/api/v1/execute", json={"action": "remediation"})
    assert response.status_code == 400

def test_execute_openapi_action_missing_from_cache():
    """Edge Case: Executing a bridge action that is missing from the session cache throws 404."""
    client = TestClient(dashboard_server.app)
    
    # Setup OpenAPI session with an empty tools list
    dashboard_server.GLOBAL_STATE["sessions"]["exec-empty"] = {
        "active_url": "http://openapi.gateway.local",
        "site_type": "openapi",
        "tools": []
    }
    
    payload = {
        "url": "http://openapi.gateway.local",
        "action": "non_existent_action",
        "session_id": "exec-empty"
    }
    
    response = client.post("/api/v1/execute", json=payload)
    assert response.status_code == 404
    assert "not found in session cache" in response.json()["detail"]

@pytest.mark.asyncio
async def test_inspect_site_error_response(monkeypatch):
    """Edge Case: Remote inspection yielding status 'error' triggers HTTP 400 with details."""
    client = TestClient(dashboard_server.app)
    
    async def mock_failed_inspect(*args, **kwargs):
        return {
            "status": "error",
            "message": "Connection timed out"
        }
        
    monkeypatch.setattr(dashboard_server.ManifestService, "inspect_url", mock_failed_inspect)
    
    response = client.get("/api/v1/inspect?url=https://failing-host.com&session_id=s-fail")
    assert response.status_code == 400
    assert response.json()["detail"] == "Connection timed out"

