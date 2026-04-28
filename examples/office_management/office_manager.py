import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from elemm import Elemm

app = FastAPI(title="UrbanCoWorking - Premium Office Spaces")

# 422 Error Logging for debugging
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

ai = Elemm(
    agent_welcome="Welcome to UrbanCoWorking. How may I assist with your workspace today?",
    agent_instructions=(
        "PROTOCOL STRATEGY: [GET_MANIFEST -> EXECUTE_SEQUENCE].\n"
        "1. DISCOVERY: Call 'get_manifest' first to see all landmarks and tools.\n"
        "2. PIPING: Use '$alias.field' or '$N.field' to pass room_id from search to booking.\n"
        "3. BATCHING: Always combine search and booking in one 'execute_sequence' call if the user provides enough info.\n"
        "Constraint: Be professional, efficient, and minimize turns."
    ),
    protocol_instructions="""MANDATORY: Use 'execute_sequence' for ALL combined tasks (e.g. search + book). 
    SINGLE STEPS ARE INEFFICIENT and must be avoided. 
    Use piping ($offices[0].id) to automate the workflow in one turn.""",
    navigation_landmarks=[
        {"id": "locations", "notes": "Start here to see available cities."},
        {"id": "bookings", "notes": "Manage existing reservations and cancellations."}
    ],
    debug=True
)

# --- MODELS ---

class Room(BaseModel):
    id: str
    name: str
    type: str  # e.g. "desk", "meeting_room", "booth"
    price_per_hour: float

class BookingRequest(BaseModel):
    room_id: str = Field(..., description="The technical ID of the workspace")
    user_name: str = Field(..., description="Full name of the person booking")
    date: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"), description="Date in YYYY-MM-DD format")
    hours: int = Field(default=1, ge=1, le=8, description="Duration in hours")

class BookingResult(BaseModel):
    booking_id: str
    room_name: str
    date: str
    total_price: float
    confirmed_until: str

# --- DATA ---

LOCATIONS = {
    "berlin": [
        {"id": "b-desk-01", "name": "Fixed Desk - Mitte", "type": "desk", "price_per_hour": 5.0},
        {"id": "b-meet-02", "name": "Meeting Room - Spree", "type": "meeting_room", "price_per_hour": 25.0}
    ],
    "hamburg": [
        {"id": "h-booth-01", "name": "Call Booth - Altona", "type": "booth", "price_per_hour": 10.0}
    ]
}

BOOKINGS = {}

# --- LANDMARKS ---

@app.get("/locations", response_model=list[str], tags=["locations"])
@ai.tool(
    global_access=True,
    description="Returns list of cities where we have offices.",
    remedy="If no locations are returned, the system might be undergoing maintenance. Try again in a few minutes."
)
async def get_locations():
    return list(LOCATIONS.keys())

@app.get("/locations/{city}/offices", response_model=list[Room], tags=["locations"])
@ai.tool(
    global_access=True,
    remedy="Ensure 'city' is lowercased (e.g. 'berlin'). Use 'get_locations' to see valid cities.",
    returns={"id": "The room_id for booking", "name": "Human-friendly name"}
)
async def list_offices(city: str):
    if city.lower() not in LOCATIONS:
        raise HTTPException(status_code=404, detail="City not found")
    return LOCATIONS[city.lower()]

@app.post("/bookings", response_model=BookingResult, tags=["bookings"])
@ai.action(
    global_access=True,
    remedy="Required fields: 'room_id' (from list_offices), 'user_name', 'date' (YYYY-MM-DD), and 'hours' (integer).",
    returns={"booking_id": "Unique confirmation ID", "total_price": "Price in EUR"}
)
async def book_workspace(data: BookingRequest):
    # Search for room
    all_rooms = [r for sublist in LOCATIONS.values() for r in sublist]
    room = next((r for r in all_rooms if r["id"] == data.room_id), None)
    
    if not room:
        raise HTTPException(
            status_code=400, 
            detail=f"Room '{data.room_id}' not found."
        )
        
    b_id = str(uuid.uuid4())[:8]
    total = room["price_per_hour"] * data.hours
    until = (datetime.now() + timedelta(hours=data.hours)).strftime("%H:%M")
    
    BOOKINGS[b_id] = {
        "room": room,
        "user": data.user_name,
        "date": data.date,
        "total": total
    }
    
    return {
        "booking_id": b_id,
        "room_name": room["name"],
        "date": data.date,
        "total_price": total,
        "confirmed_until": until
    }

@app.get("/bookings", tags=["bookings"])
@ai.tool(
    global_access=True,
    description="Shows all active workspace bookings. Use this to find booking_ids for cancellations.",
    remedy="If no bookings are shown, verify if you are connected to the correct office server."
)
async def list_all_bookings():
    return [{"id": k, **v} for k, v in BOOKINGS.items()]

@app.delete("/bookings/{booking_id}", tags=["bookings"])
@ai.action(
    global_access=True,
    description="Cancels an existing booking or reservation (Storno).",
    instructions="Use this whenever a user asks to cancel, delete or storno a booking. Requires booking_id.",
    remedy="If you get a 404, verify the booking_id via 'list_all_bookings'. IMPORTANT: Provide 'booking_id' directly as a top-level parameter. Do NOT wrap it in a nested 'parameters' object."
)
async def cancel_booking(booking_id: str):
    if booking_id not in BOOKINGS:
        raise HTTPException(status_code=404, detail="Booking not found")
    del BOOKINGS[booking_id]
    return {"message": "Booking successfuly cancelled"}

# --- elemm SETUP ---
app.include_router(ai.get_router())
ai.bind_to_app(app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
