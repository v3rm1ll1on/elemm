from fastapi import FastAPI, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from enum import Enum
from typing import List, Optional, Dict
from elemm import Elemm

app = FastAPI(title="Nexus-Corp Elemm-API")
# 1. Initialize Elemm - handles discovery, security shielding, and self-healing.
ai = Elemm(
    agent_welcome="Nexus-OS AI Core online. Systems operational.",
    protocol_instructions="Focus on the Logistics and Power modules first."
)

class ResourceStatus(str, Enum):
    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"

class Location(BaseModel):
    sector: str = Field(..., description="The sector ID (e.g. S-7)")
    coordinates: str = Field(..., description="GPS coordinates")
    security_level: int = Field(1, ge=1, le=10)

class Resource(BaseModel):
    id: str = Field(..., description="Unique hardware ID")
    name: str
    type: str
    status: ResourceStatus
    location: Location
    tags: List[str] = []

RESOURCES = [
    {
        "id": "R-101", "name": "Fusion Core A", "type": "Power", 
        "status": ResourceStatus.ACTIVE, "location": {"sector": "S-7", "coordinates": "12.4, 44.1", "security_level": 5},
        "tags": ["core", "high-power"]
    }
]

@ai.tool(id="query_resources", type="read")
@app.get("/resources", response_model=List[Resource])
async def list_resources(
    type: Optional[str] = None, 
    status: Optional[ResourceStatus] = None,
    min_security: int = Query(0, ge=0)
):
    """List and filter corp resources."""
    return RESOURCES

@ai.tool(id="get_resource_detail", type="read")
@app.get("/resources/{id}", response_model=Resource)
async def get_resource(id: str):
    res = next((r for r in RESOURCES if r["id"] == id), None)
    if not res: raise HTTPException(404)
    return res

@ai.action(
    id="deploy_resource", 
    type="write", 
    remedy="If 422 error occurs, it means the Sector ID is invalid. Valid sectors are S-1 to S-10. Call list_types to verify."
)
@app.post("/resources")
async def create_resource(res: Resource):
    if "AREA-51" in str(res.location.sector):
        raise HTTPException(status_code=422, detail="Invalid Sector Access")
    RESOURCES.append(res.model_dump())
    return {"status": "created", "id": res.id}

@ai.action(id="modify_status", type="write", instructions="Only change to OFFLINE during maintenance.")
@app.patch("/resources/{id}/status")
async def update_status(id: str, status: ResourceStatus):
    return {"status": "updated"}

@ai.tool(id="list_types", type="navigation")
@app.get("/categories")
async def list_categories():
    return ["Power", "Compute", "Storage", "Logistics"]

@ai.landmark(id="nexus_analytics", type="read")
@app.get("/analytics/usage")
async def get_usage_stats():
    return {"uptime": "99.9%", "load": "high", "nodes": 128}

@ai.landmark(id="system_health", type="read", hidden=True)
@app.get("/health")
async def health_check():
    """Internal health check. Not relevant for AI."""
    return {"status": "ok", "timestamp": "2026-04-15T12:00:00Z"}

@ai.landmark(id="debug_dump", type="read", hidden=True)
@app.get("/debug/inventory")
async def debug_inventory():
    """Internal raw dump. Too much noise for LLM."""
    return {"raw_data": "..."}

# 2. Bind and you're done! 
# elemm automatically extracts Nested Models, Enums, Field-Descriptions, 
# and even Query constraints like "ge=0".
app.include_router(ai.get_router())
ai.bind_to_app(app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
