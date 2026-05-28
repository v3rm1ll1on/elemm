# Copyright (C) 2026 Marc Stöcker
# Website: https://elemm.dev
#
# This program is licensed under the Business Source License 1.1 (BSL 1.1).
# See the LICENSE file in the root directory for details.

import pytest
from fastapi import FastAPI, Query
from fastapi.testclient import TestClient
from elemm.core.manager import AIProtocolManager
from elemm.gateways.fastapi import FastAPIGateway

def test_fastapi_repair_handler():
    app = FastAPI()
    manager = AIProtocolManager(instructions="Test")
    
    @app.get("/tool")
    @manager.bind("my_tool")
    def my_tool(param: str = Query(...)):
        return {"ok": True}
    
    gateway = FastAPIGateway(manager)
    gateway.bind_to_app(app)
    
    client = TestClient(app)
    
    # Aufruf ohne erforderlichen Parameter -> Sollte 422 Repair auslösen
    resp = client.get("/tool")
    assert resp.status_code == 422
    data = resp.json()
    assert data["status"] == "error"
    assert "remedy" in data
    assert "inspect_landmark" in data["remedy"]

def test_fastapi_well_known():
    app = FastAPI()
    manager = AIProtocolManager(instructions="Global Instructions")
    gateway = FastAPIGateway(manager)
    gateway.bind_to_app(app)
    
    client = TestClient(app)
    resp = client.get("/.well-known/elemm-manifest.md")
    assert resp.status_code == 200
    assert "ELEMM v2 SECURE INTERFACE" in resp.text
    assert "Global Instructions" in resp.text # Manifest shows instructions in v2