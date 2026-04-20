import pytest
from fastapi import FastAPI, Body, Query
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field
from elemm import Elemm

class Order(BaseModel):
    id: str
    amount: int = Field(..., ge=1, le=100)

@pytest.fixture
def repair_app():
    app = FastAPI()
    ai = Elemm(agent_welcome="Welcome")
    
    # 1. Action with Body and Remedy
    @app.post("/order")
    @ai.action(id="place_order", remedy="Amount must be 1-100.")
    async def place_order(order: Order):
        return {"status": "ok"}
    
    # 2. Tool with Path and Query Params
    @app.get("/items/{item_id}")
    @ai.tool(id="get_item", remedy="Use a valid UUID for item_id and a positive priority.")
    async def get_item(item_id: int, priority: int = Query(..., ge=1)):
        return {"id": item_id}

    # 3. Non-Landmark Route (Control Group)
    @app.get("/legacy")
    async def legacy_route(val: int):
        return {"val": val}

    ai.bind_to_app(app)
    return app

def test_remedy_injection_basic(repair_app):
    client = TestClient(repair_app)
    response = client.post("/order", json={"id": "O-1", "amount": 999})
    data = response.json()
    assert data["managed_by"] == "elemm"
    assert data["remedy"] == "Amount must be 1-100."

def test_remedy_injection_path_and_query(repair_app):
    client = TestClient(repair_app)
    
    # Invalid Path Param (string instead of int)
    response = client.get("/items/abc?priority=5")
    assert response.status_code == 422
    data = response.json()
    assert data["remedy"] == "Use a valid UUID for item_id and a positive priority."
    
    # Invalid Query Param (priority < 1)
    response = client.get("/items/123?priority=0")
    assert response.status_code == 422
    assert response.json()["remedy"] == "Use a valid UUID for item_id and a positive priority."

def test_noise_detection_details(repair_app):
    client = TestClient(repair_app)
    # Missing required field 'id' + Hallucinated field 'color'
    response = client.post("/order", json={"amount": 50, "color": "blue"})
    data = response.json()
    assert "noise_warning" in data
    assert "color" in data["noise_warning"]
    assert "remedy" in data

def test_fallback_for_non_landmarks(repair_app):
    client = TestClient(repair_app)
    # This route is NOT a landmark, should return standard error without elemm enrichment
    response = client.get("/legacy?val=abc")
    assert response.status_code == 422
    data = response.json()
    # Should NOT contain elemm fields
    assert "managed_by" not in data
    assert "remedy" not in data
    # But should still contain 'detail' (default FastAPI)
    assert "detail" in data

def test_no_enrichment_on_success(repair_app):
    client = TestClient(repair_app)
    response = client.post("/order", json={"id": "O-1", "amount": 50})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
