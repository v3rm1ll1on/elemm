import os
import asyncio
from typing import Dict, Any, List
from elemm.core.manager import AIProtocolManager
from elemm.core.registry import MetadataRegistry
from elemm.gateways.fastapi import FastAPIGateway

class UltraMansionState:
    def __init__(self):
        self.security = {
            "armed": True,
            "mode": "Away",
            "siren_status": "idle",
            "windows": {"kitchen": "closed", "basement": "closed", "living_room": "open"}
        }
        self.lighting = {
            "kitchen": {"color": "#FFFFFF", "brightness": 100, "pulse": False},
            "living_room": {"color": "#00FF00", "brightness": 50, "pulse": False},
            "office": {"color": "#0000FF", "brightness": 80, "pulse": False},
            "hallway": {"color": "#FFFFFF", "brightness": 100, "pulse": False},
            "basement": {"color": "#FFFFFF", "brightness": 100, "pulse": False},
            "garage": {"color": "#FFFFFF", "brightness": 100, "pulse": False}
        }
        self.climate = {
            "kitchen": {"temp": 21.0, "humidity": 45, "co2": 450},
            "living_room": {"temp": 22.5, "humidity": 40, "co2": 520},
            "office": {"temp": 18.0, "humidity": 50, "co2": 400},
            "hallway": {"temp": 19.0, "humidity": 40, "co2": 380},
            "basement": {"temp": 16.0, "humidity": 65, "co2": 350},
            "garage": {"temp": 12.0, "humidity": 55, "co2": 300}
        }
        self.rooms = {
            "living_room": {"tv": "off", "main_light": "off", "shutter": "closed"},
            "kitchen": {"coffee_machine": "off", "oven": "off", "fridge_boost": "off", "light": "off"},
            "basement": {"washer": "idle", "dryer": "idle", "water_sensor": "dry"},
            "garage": {"garage_door": "closed", "ev_charger": "off"},
            "garden": {"irrigation_west": "off", "irrigation_east": "off", "mower": "docked"},
            "hallway": {"lock": "locked", "light": "off"}
        }

ULTRA_MANSION = UltraMansionState()

def run_mansion():
    config_path = os.path.join(os.path.dirname(__file__), "landmarks.yaml")
    registry = MetadataRegistry(config_path)
    manager = AIProtocolManager(registry=registry)

    # --- SECURITY ---
    @manager.landmark("security:get_full_status")
    async def get_security():
        return {
            "alarm": {"armed": ULTRA_MANSION.security["armed"], "mode": ULTRA_MANSION.security["mode"]},
            "windows_open": [k for k, v in ULTRA_MANSION.security["windows"].items() if v == "open"],
            "smoke_detectors": "Operational"
        }

    @manager.landmark("security:arm")
    async def arm_security(mode: str):
        mode = mode.lower()
        if mode not in ["home", "away", "night", "panic"]:
            return {"status": "error", "message": f"Invalid security mode '{mode}'."}
        ULTRA_MANSION.security["armed"] = True
        ULTRA_MANSION.security["mode"] = mode.capitalize()
        return {"status": "success", "active_sensors": 24}

    @manager.landmark("security:siren_test")
    async def siren_test():
        return {"status": "test_completed", "decibel_peak": 115.5}

    # --- LIGHTING ---
    @manager.landmark("lighting:set_color")
    async def set_color(zone: str, color_hex: str):
        zone = zone.lower()
        if zone in ULTRA_MANSION.lighting:
            ULTRA_MANSION.lighting[zone]["color"] = color_hex
            return {"status": "success", "color": color_hex}
        return {"status": "error", "message": f"Zone '{zone}' not found."}

    @manager.landmark("lighting:pulse_effect")
    async def pulse_light(zone: str, color: str, speed: float):
        return {"status": "success", "message": f"Pulsing {color} in {zone}"}

    # --- CLIMATE ---
    @manager.landmark("climate:get_status")
    async def get_status(room: str):
        room = room.lower()
        if room in ULTRA_MANSION.climate:
            c = ULTRA_MANSION.climate[room]
            return {"temp": c["temp"], "humidity": c["humidity"], "co2_ppm": c["co2"], "status": "Excellent"}
        return {"status": "error", "message": f"Sensors for '{room}' offline."}

    @manager.landmark("climate:set_target_temp")
    async def set_target_temp(room: str, temp: float):
        room = room.lower()
        if room in ULTRA_MANSION.climate:
            ULTRA_MANSION.climate[room]["temp"] = temp
            return {"status": "success", "current_temp": temp}
        return {"status": "error", "message": f"Climate control for '{room}' unavailable."}

    # --- SPECIAL TOOLS (Register FIRST) ---
    @manager.landmark("basement:flood_sensor")
    async def basement_flood():
        return {"status": "OK", "moisture_level": 2}

    @manager.landmark("basement:laundry")
    async def basement_laundry(machine: str, action: str):
        return {"status": "success", "message": f"Machine {machine} set to {action}"}

    @manager.landmark("garden:irrigation")
    async def garden_irrigation(zone: str, duration_min: float):
        return {"status": "success", "message": f"Watering {zone} for {duration_min}m"}

    # --- DYNAMIC ROOM CONTROLS ---
    def create_handler(room_id: str):
        async def handler(device: str, action: str, brightness: float = None):
            rid = room_id.lower()
            dev = device.lower()
            if rid in ULTRA_MANSION.rooms:
                for k in ULTRA_MANSION.rooms[rid].keys():
                    if k.lower() == dev:
                        ULTRA_MANSION.rooms[rid][k] = action
                        msg = f"{k} set to {action}"
                        if brightness is not None: msg += f" with {brightness}% brightness"
                        return {"status": "success", "message": msg}
                return {"status": "error", "message": f"Device '{device}' not found in {room_id}."}
            return {"status": "error", "message": f"Room '{room_id}' not found."}
        return handler

    for r in ULTRA_MANSION.rooms.keys():
        manager.landmark(f"{r}:control")(create_handler(r))

    # Launch
    import sys
    if "--fastapi" in sys.argv:
        from fastapi import FastAPI
        import uvicorn
        app = FastAPI(title="Vigilix-Ultra-Mansion-Final-v2")
        gateway = FastAPIGateway(manager)
        gateway.bind_to_app(app)
        
        port = 8002
        print(f"Starting MEGA PIPE READY MANSION (FastAPI) on http://localhost:{port}")
        uvicorn.run(app, host="0.0.0.0", port=port)
    else:
        # Native MCP Server
        from elemm.gateways.mcp_server import MCPGateway
        server = MCPGateway(manager, server_name="SmartHome-v2")
        print("Starting SmartHome v2 (Native MCP) via STDIO", file=sys.stderr)
        asyncio.run(server.run_stdio())

if __name__ == "__main__":
    run_mansion()
