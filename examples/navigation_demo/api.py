from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from elemm.fastapi import FastAPIProtocolManager

# 1. Define metadata for our groups (Modules)
# elemm will use these to create Navigation Landmarks.
tags_metadata = [
    {
        "name": "Sales",
        "description": "Operations related to customer orders and sales analytics.",
    },
    {
        "name": "Inventory",
        "description": "Warehouse operations, stock management, and logistics.",
    },
]

app = FastAPI(
    title="Nexus Corp Enterprise API",
    openapi_tags=tags_metadata
)

# 2. Setup elemm
ai = FastAPIProtocolManager(
    agent_welcome="Welcome to Nexus Corp. Use module exploration to save context.",
    debug=True
)

class Order(BaseModel):
    id: str
    item: str
    amount: int

# --- SALES MODULE ---

@ai.landmark(id="get_orders", type="read")
@app.get("/sales/orders", tags=["Sales"])
async def get_orders():
    """List all recent sales orders."""
    return [{"id": "ORD-1", "item": "AI-Processor", "amount": 5}]

@ai.landmark(id="create_order", type="write")
@app.post("/sales/orders", tags=["Sales"])
async def create_order(order: Order):
    """Create a new customer order."""
    return {"status": "created", "order_id": order.id}

# --- INVENTORY MODULE ---

@ai.landmark(id="check_stock", type="read")
@app.get("/inventory/stock", tags=["Inventory"])
async def check_stock(item_id: str):
    """Check availability of an item in the warehouse."""
    return {"item_id": item_id, "status": "In Stock", "count": 42}

@ai.landmark(id="update_stock", type="write")
@app.patch("/inventory/stock", tags=["Inventory"])
async def update_stock(item_id: str, count: int):
    """Adjust stock levels manually."""
    return {"item_id": item_id, "new_count": count}

# --- UNGROUPED (Global) ---

@ai.landmark(id="sys_status", type="read", global_access=True)
@app.get("/status", tags=["Inventory"]) # It has a tag, but should still be in Root
async def get_status():
    """Global system health check."""
    return {"status": "all systems operational"}

# Bind elemm to the app
app.include_router(ai.get_router())

@app.on_event("startup")
async def startup():
    ai.bind_to_app(app)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)
