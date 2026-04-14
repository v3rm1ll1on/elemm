import json
from elemm import FastAPIProtocolManager
from fastapi import FastAPI, Header
from pydantic import BaseModel

app = FastAPI(title="Demo App")
ai = FastAPIProtocolManager(agent_welcome="Welcome to the Support-OS.")

class Ticket(BaseModel):
    title: str
    priority: int = 1

@ai.landmark(id="get_categories", type="navigation")
@app.get("/categories")
async def list_cats():
    return ["Tech", "Billing", "General"]

@ai.landmark(id="create_ticket", type="write", remedy="If 400, ask for a clearer title.")
@app.post("/tickets")
async def create(ticket: Ticket, auth: str = Header(...)):
    return {"id": "123", "status": "created"}

# Register and bind
app.include_router(ai.get_router())
ai.bind_to_app(app)

# Generate Real Outputs
openapi = app.openapi()
landmarks = ai.get_manifest()

print("--- OPENAPI.JSON ---")
print(json.dumps(openapi, indent=2))
print("\n--- LLM-LANDMARKS.JSON ---")
print(json.dumps(landmarks, indent=2))
