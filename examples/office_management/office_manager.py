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
    agent_instructions="Concierge-style support: Provide warm, elegant booking assistance and only confirm reservations via tool-issued IDs.",
    protocol_instructions="Verify availability via 'list_offices' before booking.",
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

@app.get("/locations", response_model=list[str])
@ai.tool(
    id="get_locations", 
    global_access=True,
    groups=["locations"],
    description="Returns list of cities where we have offices.",
    remedy="If no locations are returned, the system might be undergoing maintenance. Try again in a few minutes."
)
async def get_locations():
    return list(LOCATIONS.keys())

@app.get("/locations/{city}/offices", response_model=list[Room])
@ai.tool(
    id="list_offices", 
    global_access=True,
    groups=["locations"],
    description="Lists available workspaces in a city. REQUIRED PARAMETER: 'city' (e.g., 'berlin').",
    remedy="If you get a 404, ensure you are using the parameter name 'city' and NOT 'location'. Also, verify the city name via 'get_locations'."
)
async def list_offices(city: str):
    if city.lower() not in LOCATIONS:
        raise HTTPException(status_code=404, detail="City not found")
    return LOCATIONS[city.lower()]

@app.post("/bookings", response_model=BookingResult)
@ai.action(
    id="book_workspace",
    global_access=True,
    groups=["bookings"],
    description="Book a workspace. REQUIRED PARAMETERS: room_id, user_name, date, hours (int).",
    instructions="Process each booking separately. You MUST call this tool to confirm any booking.",
    remedy="If you get a 400/422 error, ensure you use 'room_id' and 'hours' (integer). DO NOT use 'start_time', 'duration_hours' or 'city' in this call."
)
async def book_room(data: BookingRequest):
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

@app.get("/bookings")
@ai.tool(
    id="list_all_bookings", 
    global_access=True,
    groups=["bookings"],
    description="Shows all active workspace bookings. Use this to find booking_ids for cancellations.",
    remedy="If no bookings are shown, verify if you are connected to the correct office server."
)
async def list_all_bookings():
    return [{"id": k, **v} for k, v in BOOKINGS.items()]

@app.delete("/bookings/{booking_id}")
@ai.action(
    id="cancel_booking", 
    global_access=True,
    groups=["bookings"],
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
