from fastapi import FastAPI, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from enum import Enum
from typing import List, Optional, Dict

app = FastAPI(title="Nexus-Corp Legacy API")

class ResourceStatus(str, Enum):
    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"

class Location(BaseModel):
    sector: str
    coordinates: str
    security_level: int = 1

class Resource(BaseModel):
    id: str
    name: str
    type: str
    status: ResourceStatus
    location: Location
    tags: List[str] = []

RESOURCES = [
    {
        "id": "R-101", "name": "Fusion Core A", "type": "Power", 
        "status": ResourceStatus.ACTIVE, "location": {"sector": "S-7", "coordinates": "12.4, 44.1"},
        "tags": ["core", "high-power"]
    }
]

@app.get("/resources", response_model=List[Resource])
async def list_resources(
    type: Optional[str] = None, 
    status: Optional[ResourceStatus] = None,
    min_security: int = Query(0, ge=0)
):
    """List and filter corp resources."""
    return RESOURCES

@app.get("/resources/{id}", response_model=Resource)
async def get_resource(id: str):
    res = next((r for r in RESOURCES if r["id"] == id), None)
    if not res: raise HTTPException(404)
    return res

@app.post("/resources")
async def create_resource(res: Resource):
    RESOURCES.append(res.dict())
    return {"status": "created", "id": res.id}

@app.patch("/resources/{id}/status")
async def update_status(id: str, status: ResourceStatus):
    return {"status": "updated"}

@app.get("/categories")
async def list_categories():
    return ["Power", "Compute", "Storage", "Logistics"]

@app.get("/analytics/usage")
async def get_usage_stats():
    return {"uptime": "99.9%", "load": "high", "nodes": 128}

@app.get("/health")
async def health_check():
    """Technical health check."""
    return {"status": "ok"}

@app.get("/debug/inventory")
async def debug_inventory():
    """Technical debug output."""
    return {"raw_data": "..."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
