from fastapi import FastAPI, HTTPException, Request, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum
from elemm.fastapi import FastAPIProtocolManager

app = FastAPI(title="SmartHome AI Control", version="1.0.0")

# --- elemm configuration ---
ai = FastAPIProtocolManager(
    agent_instructions="Welcome to the SmartHome Matrix. You are an autonomous controller. Do NOT ask the user for device IDs if you can find them via discovery tools.",
    protocol_instructions=(
        "### SMART HOME PROTOCOL RULES ###\n"
        "1. **MANDATORY DISCOVERY**: Use 'list_rooms' and 'list_devices' to map the environment before adjusting states.\n"
        "2. **ID PRECISION**: Always use the exact 'device_id' (e.g., 'heat-1') provided by the registry.\n"
        "3. **PARAMETER VALIDATION**: Temperatures must be within the 18-24 range. Lighting uses boolean states.\n"
    ),
    navigation_landmarks=[
        {"id": "discovery", "notes": "House layout and device registry. Access rooms and list available hardware."},
        {"id": "smart_control", "notes": "Direct control for heating, lighting and appliances. Requires valid device_id."},
        {"id": "analytics", "notes": "Energy consumption metrics and system status reports."}
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
    ]
}

# --- API Routes ---

@app.get("/rooms", tags=["discovery"])
@ai.tool(
    id="list_rooms", 
    global_access=True,
    instructions="Get the list of rooms before trying to find devices."
)
def get_rooms():
    """Returns a list of all rooms in the smart home."""
    return list(DB.keys())

@app.get("/devices/{room_id}", response_model=List[Device], tags=["discovery"])
@ai.tool(
    id="list_devices", 
    global_access=True,
    description="Lists all smart devices (Lights, Heating, Espresso Machine, etc.) in a room.",
    instructions="You MUST provide the 'room_id' (e.g., 'living-room') as a parameter. Look at 'list_rooms' output first."
)
def get_devices(room_id: str):
    """Lists all smart devices in a specific room."""
    if room_id not in DB:
        raise HTTPException(
            status_code=404, 
            detail={
                "message": f"Room '{room_id}' not found.",
                "remedy": "Call 'list_rooms' to see the exact valid room IDs."
            }
        )
    return DB[room_id]

@app.post("/devices/{device_id}/control", tags=["smart_control"])
@ai.action(
    id="control_device", 
    global_access=True,
    instructions="Updates device status. Use 'device_id' (e.g., 'heat-1') and provide 'temperature' (18-24) or 'is_on' (boolean).",
    remedy="If it fails, ensure you use 'device_id' (not 'device') and 'temperature' (not 'set_temperature')."
)
def control_device(device_id: str, request: ControlRequest):
    """Updates the status or temperature of a device."""
    # Check fridge safety only if is_on is explicitly set to False
    if "fridge" in device_id and request.is_on is False:
        raise HTTPException(
            status_code=403, 
            detail={
                "message": "Safety Lock: Cannot turn off the fridge via AI.",
                "remedy": "This is a hardware safety restriction. You cannot turn off cooling appliances."
            }
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
            detail={
                "message": f"Device '{device_id}' not found.",
                "remedy": f"Verify the device ID. Use 'list_devices' for the specific room to find the correct ID."
            }
        )

    # Update power status if provided
    if request.is_on is not None:
        device_found.status = DeviceStatus.ON if request.is_on else DeviceStatus.OFF
        
    # Update temperature if provided
    if request.temperature is not None:
        device_found.temperature = request.temperature
    
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
@ai.tool(id="energy_report", instructions="Use this to warn the user if power usage is too high (total > 1000W).")
def energy_summary():
    """Returns the total energy consumption of the house."""
    total = sum(d.power_usage for devices in DB.values() for d in devices)
    return {"total_watts": total, "status": "nominal" if total < 1000 else "warning"}

# --- AI Protocol Integration ---
ai.bind_to_app(app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
