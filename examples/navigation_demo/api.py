from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn
from elemm import Elemm

# 1. Define metadata for our groups (Modules)
# Elemm uses these to create Navigation Landmarks automatically.
tags_metadata = [
    {
        "name": "Market & Sales", # Special Character test ('&')
        "description": "Operations related to customer orders and sales analytics.",
    },
    {
        "name": "Warehouse",
        "description": "Stock management and logistics.",
    },
]

app = FastAPI(
    title="Elemm Enterprise Hub",
    openapi_tags=tags_metadata
)

# 2. Initialize Elemm
ai = Elemm(
    agent_welcome="Welcome to the Enterprise Hub. Navigate via modules to save token context.",
    debug=True
)

class Order(BaseModel):
    id: str = Field(..., description="ID starting with 'ORD-'")
    amount: int = Field(..., ge=1, le=100)

# --- SALES MODULE ---

@ai.tool(id="get_orders")
@app.get("/sales/orders", tags=["Market & Sales"])
async def get_orders():
    """List all recent sales orders."""
    return [{"id": "ORD-1", "item": "AI-Processor", "amount": 5}]

@ai.action(
    id="create_order", 
    remedy="Ensure ID starts with 'ORD-' and amount is between 1 and 100."
)
@app.post("/sales/orders", tags=["Market & Sales"])
async def create_order(order: Order):
    """Create a new customer order."""
    if not order.id.startswith("ORD-"):
        raise HTTPException(status_code=422, detail="Invalid ID format.")
    return {"status": "created", "order_id": order.id}

# --- WAREHOUSE MODULE ---

@ai.tool(id="check_stock")
@app.get("/inventory/stock", tags=["Warehouse"])
async def check_stock(item_id: str):
    """Check availability of an item."""
    return {"item_id": item_id, "count": 42}

@ai.action(
    id="update_stock",
    instructions="Only use this if stock level is below 10."
)
@app.patch("/inventory/stock", tags=["Warehouse"])
async def update_stock(item_id: str, count: int):
    """Adjust stock levels manually."""
    return {"item_id": item_id, "new_count": count}

# --- GLOBAL ACCESS ---

@ai.tool(id="sys_status", global_access=True)
@app.get("/status")
async def get_status():
    """Global system health check. Visible everywhere."""
    return {"status": "all systems operational"}

# --- BINDING ---

ai.bind_to_app(app)
# This also exposes /.well-known/llm-landmarks.json
app.include_router(ai.get_router())

if __name__ == "__main__":
    print("\n--- Elemm Demo Server ---")
    print("Navigation: http://localhost:8000/.well-known/llm-landmarks.json")
    print("Market Access: http://localhost:8000/.well-known/llm-landmarks.json?group=Market+and+Sales")
    uvicorn.run(app, host="0.0.0.0", port=8000)
