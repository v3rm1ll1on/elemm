from fastapi import FastAPI, HTTPException, Request, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum
from elemm import Elemm

app = FastAPI(title="SmartHome AI Control", version="1.0.0")

# --- elemm configuration ---
ai = Elemm(
    agent_instructions=(
        "PROTOCOL STRATEGY: [ONE-SHOT MANDATE].\n"
        "1. ASSUME: If a room is mentioned (e.g. 'living room'), ASSUME room_id='living-room' immediately.\n"
        "2. ONE-TURN: Call [find_device -> control_device] in your VERY FIRST turn after get_manifest.\n"
        "3. NO VERIFICATION: Do NOT call 'list_rooms' or 'list_devices' first. Discovery-only turns are forbidden."
    ),
    protocol_instructions=(
        "INTEGRITY MANDATE: Control tools (control_device) have a HARD DEPENDENCY on discovery tools (find_device).\n"
        "You MUST provide a data-pipeline in 'execute_sequence'.\n"
        "EXAMPLE: find_device(alias='h') -> control_device(device_id='$h.id')."
    ),
    navigation_landmarks=[
        {"id": "discovery", "notes": "House layout and device registry. Use this for room-based discovery."},
        {"id": "smart_control", "notes": "Direct control. Requires valid device_id."},
        {"id": "analytics", "notes": "Energy consumption metrics."}
    ]
)

# --- Data Models ---

class DeviceStatus(str, Enum):
    ON = "on"
    OFF = "off"
    STANDBY = "standby"

class DeviceType(str, Enum):
    LIGHT = "light"
    HEATING = "heating"
    APPLIANCE = "appliance"
    SECURITY = "security"

class Device(BaseModel):
    id: str
    name: str
    type: DeviceType
    status: DeviceStatus
    temperature: Optional[float] = Field(None, description="Only for heating devices")
    power_usage: float = Field(..., description="Current usage in Watts")

class ControlRequest(BaseModel):
    is_on: Optional[bool] = Field(None, description="Set to true to turn on, false to turn off.")
    temperature: Optional[float] = Field(None, ge=18.0, le=24.0, description="Target temperature in Celsius (only for heating). MUST be between 18 and 24.")

# --- Mock Data ---

DB = {
    "living-room": [
        Device(id="light-1", name="Main Ceiling Light", type=DeviceType.LIGHT, status=DeviceStatus.OFF, power_usage=0.0),
        Device(id="heat-1", name="Floor Heating", type=DeviceType.HEATING, status=DeviceStatus.ON, temperature=21.5, power_usage=450.0),
    ],
    "kitchen": [
        Device(id="fridge-1", name="Smart Fridge", type=DeviceType.APPLIANCE, status=DeviceStatus.ON, power_usage=80.0),
        Device(id="coffee-1", name="Espresso Machine", type=DeviceType.APPLIANCE, status=DeviceStatus.OFF, power_usage=0.0),
    ],
    "bedroom": [
        Device(id="light-3", name="Bedside Lamp", type=DeviceType.LIGHT, status=DeviceStatus.OFF, power_usage=0.0),
        Device(id="heat-2", name="Bedroom Radiator", type=DeviceType.HEATING, status=DeviceStatus.OFF, temperature=18.0, power_usage=0.0),
    ],
    "bathroom": [
        Device(id="light-4", name="Mirror Light", type=DeviceType.LIGHT, status=DeviceStatus.OFF, power_usage=0.0),
        Device(id="water-1", name="Water Heater", type=DeviceType.APPLIANCE, status=DeviceStatus.ON, power_usage=1800.0),
    ],
    "office": [
        Device(id="light-5", name="Desk Lamp", type=DeviceType.LIGHT, status=DeviceStatus.ON, power_usage=12.0),
        Device(id="pc-1", name="Workstation", type=DeviceType.APPLIANCE, status=DeviceStatus.ON, power_usage=350.0),
    ],
    "garage": [
        Device(id="door-1", name="Garage Door", type=DeviceType.SECURITY, status=DeviceStatus.ON, power_usage=5.0),
        Device(id="cam-1", name="Entrance Camera", type=DeviceType.SECURITY, status=DeviceStatus.ON, power_usage=15.0),
    ]
}

# --- API Routes ---

@app.get("/rooms", tags=["discovery"])
@ai.tool(global_access=True, returns={"room_id": "List of valid room_id strings"})
def get_rooms():
    """Returns a list of all rooms in the smart home."""
    return list(DB.keys())

@app.get("/devices/{room_id}", response_model=List[Device], tags=["discovery"])
@ai.tool(
    global_access=True,
    remedy="Ensure 'room_id' is one of the IDs from 'list_rooms' (e.g. 'living-room').",
    returns={"id": "device_id", "name": "friendly name", "type": "heating/light/etc"}
)
def get_devices(room_id: str):
    """Lists all smart devices in a specific room."""
    if room_id not in DB:
        raise HTTPException(
            status_code=404, 
            detail=f"Room '{room_id}' not found."
        )
    return DB[room_id]

@app.get("/find-device", response_model=Device, tags=["discovery"])
@ai.tool(global_access=True, returns={"id": "The device_id", "status": "Current state"})
def find_device(room_id: str, device_type: DeviceType):
    """FAST-TRACK: Use this to avoid list_rooms/list_devices. 
    If the user mentions a room, use this tool directly in an 'execute_sequence' 
    to get the ID for 'control_device' in ONE turn. 
    Skipping this for manual discovery is an EFFICIENCY FAILURE."""
    devices = DB.get(room_id, [])
    for d in devices:
        if d.type == device_type:
            return d
    raise HTTPException(status_code=404, detail=f"No {device_type} found in {room_id}")

@app.post("/devices/{device_id}/control", tags=["smart_control"])
@ai.action(
    global_access=True,
    remedy="Ensure 'device_id' exists in the current room. Temperature must be 18.0-24.0. Note: Fridges cannot be turned off.",
    returns={"status": "Success/Error message", "device": "Updated device state object"}
)
def control_device(device_id: str, request: ControlRequest):
    """Updates the status or temperature of a device."""
    # Check fridge safety
    if "fridge" in device_id and request.is_on is False:
        raise HTTPException(
            status_code=403, 
            detail="Safety Lock: Cannot turn off the fridge via API."
        )
    
    device_found = None
    for room_devices in DB.values():
        for device in room_devices:
            if device.id == device_id:
                device_found = device
                break
        if device_found:
            break

    if not device_found:
        raise HTTPException(
            status_code=404, 
            detail=f"Device '{device_id}' not found."
        )

    # Update power status or temperature
    if request.is_on is not None:
        device_found.status = DeviceStatus.ON if request.is_on else DeviceStatus.OFF
    
    if request.temperature is not None:
        device_found.temperature = request.temperature
    
    if request.is_on is None and request.temperature is None:
        # Neither is_on nor temperature was provided
        raise HTTPException(
            status_code=400,
            detail="No valid control parameters provided."
        )
    
    # Update power usage based on current status
    if device_found.status == DeviceStatus.OFF:
        device_found.power_usage = 0.0
    else:
        if device_found.type == DeviceType.LIGHT:
            device_found.power_usage = 12.0
        elif device_found.type == DeviceType.HEATING:
            device_found.power_usage = 500.0

    return {
        "status": "success", 
        "message": f"Device {device_id} updated. Current status: {device_found.status.value}",
        "device": device_found
    }

@app.get("/energy/summary", tags=["analytics"])
@ai.tool(instructions="Use this to warn the user if power usage is too high (total > 1000W).")
def energy_summary():
    """Returns the total energy consumption of the house."""
    total = sum(d.power_usage for devices in DB.values() for d in devices)
    return {"total_watts": total, "status": "nominal" if total < 1000 else "warning"}

# --- AI Protocol Integration ---
ai.bind_to_app(app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
