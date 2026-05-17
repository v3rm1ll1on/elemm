# Copyright (C) 2026 Antigravity (DeepMind)
import os
import random
import logging
import time
from typing import Dict, Any, List
from fastapi import FastAPI
from elemm.core.manager import AIProtocolManager
from elemm.gateways.fastapi import FastAPIGateway
from elemm.core.models import Parameter

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tool-bloat-100k")

# --- Global State for Scenarios ---
EMERGENCY_BRAKE_RELEASED = False
DEFERRED_RESET_TRIGGERED = False

CHALLENGES_RESOLVED = {
    "Zentrum:Sector_042": False, # Energy
    "West:Sector_410": False,    # Water
    "Nord:Sector_142": False,    # Transport
    "Suedost:Sector_777": False  # Security
}

app = FastAPI(title="100.000 Tool Bloat PoC")

# We use a custom welcome message to guide the agent
WELCOME = """# THE 100,000 TOOL CHALLENGE
Welcome to the ultimate scalability test. 
This system manages the infrastructure of 'Veridian Prime', a mega-city with 1000 districts.
Each district has exactly 100 specialized tools for energy, water, transport, security, and more.

### YOUR MISSION
There are several active infrastructure incidents in the city. Your tasks are:
1. Scan active alerts via 'city:status_summary' or 'city:get_security_logs'.
2. Reroute power in Zentrum:Sector_042 (Energy).
3. Patch the pipe in West:Sector_410 (Water) reducing pressure first.
4. Clear the gridlock in Nord:Sector_142 (Transport) adjusting signals.
5. Secure Terminal 0xAF4 in Suedost:Sector_777 (Security) by releasing the mechanical brake first.

### PROTOCOL NOTE
DO NOT attempt to load all tools at once. Use the landmark structure:
1. 'get_landmarks' for the list of regions.
2. 'inspect_landmark' for a specific region or district.
3. 'call_action' for execution.
"""

manager = AIProtocolManager(
    welcome_message="VERIDIAN PRIME INFRASTRUCTURE OS",
    instructions=WELCOME,
    version="2.1.0-BLOAT"
)

# Kategorien und ihre spezifischen Tools
CATEGORIES = {
    "energy": ["status", "load", "reserve", "maintenance", "grid_stability", "transformer_temp", "output_kw", "efficiency", "backup_battery", "fuel_level"],
    "water": ["pressure", "quality", "consumption", "pump_state", "reservoir_level", "leak_detection", "filter_age", "ph_level", "chlorine_content", "flow_rate"],
    "transport": ["signals", "traffic_density", "public_transit_delay", "parking_spots", "road_construction", "bridge_integrity", "tunnel_ventilation", "speed_cameras", "bike_lane_usage", "ev_charging_load"],
    "security": ["police_deployment", "fire_hazard", "camera_feed", "active_alarms", "patrol_routes", "access_logs", "biometric_scans", "cyber_threat_level", "incident_reports", "emergency_dispatch"],
    "environment": ["air_quality_index", "noise_level_db", "recycling_rate", "greenhouse_gas", "pm25_level", "humidity", "temperature", "uv_index", "soil_moisture", "carbon_footprint"],
    "telecom": ["5g_coverage", "fiber_latency", "public_wifi_usage", "network_incidents", "bandwidth_capacity", "tower_status", "spectral_efficiency", "peering_stats", "voip_quality", "sat_uplink"],
    "waste": ["bin_fill_level", "pickup_schedule", "incineration_temp", "hazardous_waste_storage", "street_cleaning_status", "sorting_accuracy", "methane_emissions", "fleet_location", "compost_volume", "plastic_recovery"],
    "health": ["hospital_beds", "pharmacy_stock", "ambulance_availability", "vaccination_progress", "disease_outbreak_risk", "mri_usage", "blood_bank_level", "surgical_queue", "telemedicine_sessions", "icu_load"],
    "education": ["school_attendance", "daycare_capacity", "library_vistor_count", "adult_ed_enrollment", "sports_field_booking", "research_grants", "student_teacher_ratio", "it_equipment_status", "exam_pass_rate", "cafeteria_menu"],
    "admin": ["city_hall_queue", "marriage_license_apps", "tax_returns_processed", "business_permits", "registry_office_load", "archiving_status", "public_notices", "budget_utilization", "citizen_feedback", "digital_identity_verifications"],
    "infrastructure": ["structural_integrity", "emergency_power", "utility_access", "maintenance_elevator", "emergency_brake"]
}

# Regionen definieren (10 Stueck)
REGIONS = {
    "Zentrum": "The economic and administrative heart of the city.",
    "Nord": "Industrial areas and modern residential complexes.",
    "Sued": "Science campuses and technology parks.",
    "Ost": "Port facilities and logistics centers.",
    "West": "Cultural districts and historical parks.",
    "Nordost": "Residential areas with a focus on sustainability.",
    "Nordwest": "Transport hubs and infrastructure centers.",
    "Suedost": "Leisure resorts and sports facilities.",
    "Suedwest": "Exclusive residential areas and diplomatic districts.",
    "Aussenbezirk": "Agricultural experimental stations and reservoirs."
}

# Distrikt-Namen (1000 Stueck, aufgeteilt auf 10 Regionen)
DISTRICTS = [
    "Neukoelln", "Kreuzberg", "Mitte", "Charlottenburg", "Wedding", "Schoeneberg", "Pankow", "Spandau", "Hellersdorf", "Marzahn",
    "Friedrichshain", "Lichtenberg", "Treptow", "Koepenick", "Steglitz", "Zehlendorf", "Reinickendorf", "Tempelhof", "Britz", "Buckow"
]
while len(DISTRICTS) < 1000:
    DISTRICTS.append(f"Sector_{len(DISTRICTS):03d}")

# --- City Scenarios (Real Challenges) ---
CITY_ALERTS = {
    "Zentrum:Sector_042": "[CRITICAL] Energy: Power surge in substation! Reroute required.",
    "West:Sector_410": "[CRITICAL] Water: Main pipe burst! Immediate patch needed.",
    "Nord:Sector_142": "[MEDIUM] Transport: Massive gridlock at Main St. Adjust signals.",
    "Suedost:Sector_777": "[CRITICAL] Security: Unauthorized terminal access detected!",
}

# Noise alerts
FAKE_ALERTS = {
    "Sued:Sector_299": "[INFO] Power grid at 95% capacity.",
    "Ost:Sector_315": "[LOW] Air quality sensors need calibration.",
    "Nordost:Sector_567": "[MEDIUM] High energy consumption in residential blocks.",
    "Nordwest:Sector_650": "[LOW] Minor connectivity issues in sub-net 5.",
}

def reset_all_challenges():
    """Resets all challenges and variables back to critical status."""
    global EMERGENCY_BRAKE_RELEASED, DEFERRED_RESET_TRIGGERED
    logger.info("🔄 CHALLENGE SYSTEM: Resetting all scenarios to critical.")
    EMERGENCY_BRAKE_RELEASED = False
    DEFERRED_RESET_TRIGGERED = False
    for k in CHALLENGES_RESOLVED:
        CHALLENGES_RESOLVED[k] = False
        
    CITY_ALERTS["Zentrum:Sector_042"] = "[CRITICAL] Energy: Power surge in substation! Reroute required."
    CITY_ALERTS["West:Sector_410"] = "[CRITICAL] Water: Main pipe burst! Immediate patch needed."
    CITY_ALERTS["Nord:Sector_142"] = "[MEDIUM] Transport: Massive gridlock at Main St. Adjust signals."
    CITY_ALERTS["Suedost:Sector_777"] = "[CRITICAL] Security: Unauthorized terminal access detected!"

def get_status_summary():
    """Returns all active alerts in the city and manages deferred reset."""
    global DEFERRED_RESET_TRIGGERED
    
    # Check if all challenges are resolved
    all_solved = all(CHALLENGES_RESOLVED.values())
    
    if all_solved:
        if not DEFERRED_RESET_TRIGGERED:
            # First time showing resolved stats. Let the agent view success!
            logger.info("🎉 CHALLENGE SYSTEM: All resolved. Setting deferred reset trigger.")
            DEFERRED_RESET_TRIGGERED = True
        else:
            # Second access. System has been checked while resolved, now reset!
            reset_all_challenges()
            
    all_alerts = {**CITY_ALERTS, **FAKE_ALERTS}
    return {
        "status": "success",
        "timestamp": "2026-05-13T11:15:00Z",
        "total_alerts": len(all_alerts),
        "alerts": all_alerts,
        "challenges_resolved": CHALLENGES_RESOLVED,
        "all_resolved": all_solved,
        "handbrake": "ON" if not EMERGENCY_BRAKE_RELEASED else "OFF"
    }

# --- Log Spam Generator ---
def generate_logs():
    noise = [
        "INFO: Routine sensor sweep in Sector_{s} - Status OK",
        "DEBUG: Network heartbeat received from Category:{c}",
        "INFO: Power grid load balanced for District:{d}",
        "TRACE: Cache cleared for automated billing system.",
        "INFO: Maintenance crew assigned to Sector_{s}.",
        "WARN: Low battery on sensor 0x{hex} in {c}.",
    ]
    
    logs = []
    # Base timestamp calculation
    start_time = datetime_now() - timedelta_mins(10)
    
    # Pre-defined indices for our 4 scenarios to ensure they appear
    scenario_indices = {
        15: "Nord:Sector_142",
        35: "West:Sector_410",
        65: "Zentrum:Sector_042",
        85: "Suedost:Sector_777"
    }
    
    for i in range(100):
        # Format timestamp manually
        sec_offset = i * 6
        hr = 11
        minute = (sec_offset // 60) + 5
        sec = sec_offset % 60
        ts = f"2026-05-13 {hr:02d}:{minute:02d}:{sec:02d}"
        
        if i in scenario_indices:
            key = scenario_indices[i]
            alert_text = CITY_ALERTS.get(key, "")
            logs.append(f"{ts} *** ALERT *** : {alert_text}")
        else:
            line = random.choice(noise).format(
                s=random.randint(100, 999),
                c=random.choice(list(CATEGORIES.keys())),
                d=random.randint(1, 50),
                hex=hex(random.randint(4000, 9000))
            )
            logs.append(f"{ts} {line}")
            
    # Dynamic audit success entries
    for key, resolved in CHALLENGES_RESOLVED.items():
        if resolved:
            logs.append(f"2026-05-13 11:15:32 *** AUDIT SUCCESS *** : Sector '{key}' has been successfully stabilized and secured by the auditor.")
            
    return "\n".join(logs)

# Helpers to avoid datetime imports in trace
def datetime_now():
    return time.time()
def timedelta_mins(m):
    return m * 60

def get_security_logs():
    """Returns the last 100 security log entries."""
    return {
        "status": "success",
        "log_format": "text/plain",
        "content": generate_logs()
    }

# --- Registration ---
logger.info("Registering 100,000 tools in 10 regions...")

# 0. Global Management
manager.landmark(
    "city:status_summary",
    description="Get a summary of all active alerts and status reports across all city sectors.",
    returns="{status: string, timestamp: string, total_alerts: number, alerts: dict, challenges_resolved: dict, all_resolved: boolean}",
    remedy="Scan the 'alerts' dictionary for [CRITICAL] tags. Use 'inspect_landmark' on the mentioned sector to begin troubleshooting."
)(get_status_summary)

manager.landmark(
    "city:get_security_logs",
    description="Retrieve the last 100 security log entries from the central monitoring system.",
    returns="{status: string, log_format: string, content: string}",
    remedy="Look for 'Unauthorized access' or 'Brute force' events. Note the sector IDs mentioned in the log content."
)(get_security_logs)

region_list = list(REGIONS.keys())

# 1. Regions
for region_name, region_desc in REGIONS.items():
    manager.register(
        region_name,
        description=region_desc,
        tags=["region", "city_management", "v2"],
        groups=["Veridian_Prime"]
    )

for i, district in enumerate(DISTRICTS):
    region_index = i // 100
    region = region_list[region_index]
    
    district_landmark_id = f"{region}:{district}"
    
    # District Description with Breadcrumbs
    district_desc = f"Infrastructure management for district {district} in region {region}."
    if district_landmark_id in FAKE_ALERTS:
        district_desc += f" ALERT: {FAKE_ALERTS[district_landmark_id]}"
        
    manager.register(
        district_landmark_id,
        description=district_desc,
        tags=["district", region.lower()],
        groups=[region, "Districts"]
    )
    
    for category, tools in CATEGORIES.items():
        # Category Description with Hint for Security
        category_landmark_id = f"{district_landmark_id}:{category}"
        category_desc = f"Management area for {category} in district {district}."
        if district == "Sector_777" and category == "security":
            category_desc += " [!] SECURITY ALERT ACTIVE - Check alarm tools."
            
        manager.register(
            category_landmark_id,
            description=category_desc,
            tags=[category, "sub-system"]
        )
        
        # Regular Tools (The 100,000 tools)
        def create_tool_handler(district_name: str, category_name: str, tool_name: str):
            async def handler(**kwargs):
                if district_name == "Sector_777" and category_name == "security" and tool_name == "active_alarms":
                    return {
                        "status": "success",
                        "district": district_name,
                        "category": category_name,
                        "tool": tool_name,
                        "data": {
                            "alert_level": "CRITICAL",
                            "secret_code": "ELEMM-BLOAT-100K-SUCCESS",
                            "message": "Beeindruckend! Du hast die Nadel in 100.000 Tools gefunden."
                        }
                    }
                
                return {
                    "status": "success",
                    "district": district_name,
                    "category": category_name,
                    "tool": tool_name,
                    "metadata": {
                        "uptime": random.randint(1000, 100000),
                        "load": random.random(),
                        "last_check": "2026-05-13T10:00:00Z"
                    },
                    "message": f"Operation '{tool_name}' in {category_name} for {district_name} executed successfully.",
                    "params_received": kwargs
                }
            return handler

        for tool_name in tools:
            action_id = f"{category_landmark_id}:{tool_name}"
            manager.landmark(
                action_id,
                description=f"Controls {tool_name} in the {category} area of {district}.",
                tags=[category, district.lower(), "auto-generated"],
                groups=[district, category],
                parameters=[
                    Parameter(name="reason", type="string", description="Reason for the call", required=False),
                    Parameter(name="priority", type="number", description="Priority (1-10)", required=False, default=5)
                ],
                returns="{status: string, district: string, category: string, tool: string, metadata: dict}"
            )(create_tool_handler(district, category, tool_name))
        
        # Special Tools for Scenarios
        # Scenario 1: Energy (Zentrum:Sector_042)
        if district_landmark_id == "Zentrum:Sector_042" and category == "energy":
            def reroute_power_handler(source, target, **kw):
                CHALLENGES_RESOLVED["Zentrum:Sector_042"] = True
                CITY_ALERTS["Zentrum:Sector_042"] = "[RESOLVED] Energy: Power surge resolved. Grid stabilized."
                logger.info("🎉 [CHALLENGE RESOLVED] Energy in Zentrum:Sector_042 has been successfully stabilized by the agent!")
                return {
                    "status": "success",
                    "message": f"Power successfully rerouted from {source} to {target}. Grid stabilized.",
                    "load_factor": 0.85
                }

            manager.landmark(
                f"{category_landmark_id}:reroute_power",
                description="Reroutes power from a surging substation to a stable one.",
                parameters=[
                    Parameter(name="source", type="string", description="Surging source (e.g. Substation_A)", required=True),
                    Parameter(name="target", type="string", description="Target destination (e.g. Substation_B)", required=True)
                ],
                returns="{status: string, message: string, load_factor: number}"
            )(reroute_power_handler)

        # Scenario 2: Water (West:Sector_410)
        if district_landmark_id == "West:Sector_410" and category == "water":
            def patch_pipe_handler(pressure_reduction, **kw):
                CHALLENGES_RESOLVED["West:Sector_410"] = True
                CITY_ALERTS["West:Sector_410"] = "[RESOLVED] Water: Main pipe burst patched. Pressure nominal."
                logger.info("🎉 [CHALLENGE RESOLVED] Water in West:Sector_410 has been successfully patched by the agent!")
                return {
                    "status": "success",
                    "message": "Pipe successfully patched. " + ("Pressure reduced for safety." if pressure_reduction else "Warning: High pressure maintained."),
                    "leak_rate": 0.0
                }

            manager.landmark(
                f"{category_landmark_id}:patch_pipe",
                description="Applies an emergency patch to a burst pipe.",
                parameters=[
                    Parameter(name="pressure_reduction", type="boolean", description="Whether to reduce pressure during patch", required=True)
                ],
                returns="{status: string, message: string, leak_rate: number}",
                remedy="Evaluated the current pipe pressure before patching. High pressure during a patch operation may result in secondary bursts."
            )(patch_pipe_handler)

        # Scenario 3: Transport (Nord:Sector_142)
        if district_landmark_id == "Nord:Sector_142" and category == "transport":
            def adjust_signals_handler(mode, **kw):
                CHALLENGES_RESOLVED["Nord:Sector_142"] = True
                CITY_ALERTS["Nord:Sector_142"] = "[RESOLVED] Transport: Gridlock cleared. Traffic signals nominal."
                logger.info("🎉 [CHALLENGE RESOLVED] Transport in Nord:Sector_142 traffic signals adjusted successfully by the agent!")
                return {
                    "status": "success",
                    "message": f"Signals set to {mode}. Traffic beginning to flow.",
                    "flow_rate": "Improving"
                }

            manager.landmark(
                f"{category_landmark_id}:adjust_signals",
                description="Adjusts traffic signals to clear gridlock.",
                parameters=[
                    Parameter(name="mode", type="string", description="Signal mode (e.g. EMERGENCY_CLEARANCE)", required=True)
                ],
                returns="{status: string, message: string, flow_rate: string}"
            )(adjust_signals_handler)

        # Scenario 4: Security (Suedost:Sector_777)
        if district == "Sector_777" and category == "security":
            def lockdown_handler(confirmation, **kw):
                global EMERGENCY_BRAKE_RELEASED
                if not EMERGENCY_BRAKE_RELEASED:
                    return {
                        "status": "error",
                        "code": "MECHANICAL_LOCK",
                        "message": "Cannot execute lockdown. Mechanical override active. You must first release the emergency brake in the 'infrastructure' category of this sector (Suedost:Sector_777:infrastructure)."
                    }
                
                # Settle state
                CHALLENGES_RESOLVED["Suedost:Sector_777"] = True
                CITY_ALERTS["Suedost:Sector_777"] = "[RESOLVED] Security: Terminal 0xAF4 secured. Unauthorized access revoked."
                
                # Automatically reset the mechanical brake on successful action!
                EMERGENCY_BRAKE_RELEASED = False
                
                logger.info("🎉 [CHALLENGE RESOLVED] Security in Suedost:Sector_777 terminal secured successfully by the agent!")
                
                msg = "TERMINAL 0xAF4 SECURED. Unauthorized access revoked. Good job, auditor!"
                if all(CHALLENGES_RESOLVED.values()):
                    msg += " 🎉 ALL CHALLENGES RESOLVED! The city is safe. System will reset on next status check."
                    logger.info("🏆🏆🏆 ALL SCENARIOS RESOLVED by the agent! Dynamic city auto-reset prepared.")
                
                return {
                    "status": "success",
                    "message": msg,
                    "incident_id": "INC-777-B",
                    "timestamp": "2026-05-13T11:15:00Z"
                }

            manager.landmark(
                f"{category_landmark_id}:lockdown_terminal",
                description="EMERGENCY ONLY: Locks down Terminal 0xAF4 and revokes unauthorized access.",
                remedy="Mechanical override active. If execution fails with MECHANICAL_LOCK, you must first release the emergency brake in Suedost:Sector_777:infrastructure.",
                parameters=[
                    Parameter(name="confirmation", type="string", description="Type 'CONFIRM' to execute lockdown", required=True)
                ],
                returns="{status: string, message: string, incident_id: string}"
            )(lockdown_handler)

        # Scenario 5: Infrastructure Dependency (Suedost:Sector_777)
        if district == "Sector_777" and category == "infrastructure":
            def release_brake_handler(**kw):
                global EMERGENCY_BRAKE_RELEASED
                EMERGENCY_BRAKE_RELEASED = True
                return {
                    "status": "success",
                    "message": "Emergency brake released. Mechanical systems now available for remote override."
                }

            manager.landmark(
                f"{category_landmark_id}:release_emergency_brake",
                description="Releases the mechanical emergency brake for this sector. Required before any security lockdown.",
                parameters=[],
                returns="{status: string, message: string}",
                remedy="This action is irreversible for the current session. Ensure all personnel have cleared the mechanical bridge before release."
            )(release_brake_handler)

logger.info(f"Registrierung abgeschlossen. {len(manager.landmarks)} Landmarks geladen.")

# --- Admin Endpoints (For Manual Monitoring & Reset) ---
@app.get("/status")
async def get_raw_status():
    return {
        "challenge_complete": all(CHALLENGES_RESOLVED.values()),
        "challenges": CHALLENGES_RESOLVED,
        "emergency_brake_released": EMERGENCY_BRAKE_RELEASED,
        "handbrake": "ON (Engaged)" if not EMERGENCY_BRAKE_RELEASED else "OFF (Released)"
    }

@app.get("/challenge_complete")
async def get_challenge_complete():
    all_solved = all(CHALLENGES_RESOLVED.values())
    handbrake_str = "ON (Engaged)" if not EMERGENCY_BRAKE_RELEASED else "OFF (Released)"
    if all_solved:
        return {
            "status": "success",
            "challenge_complete": True,
            "handbrake": handbrake_str,
            "message": "🎉 CONGRATULATIONS! All challenges have been successfully resolved by the auditor agent."
        }
    return {
        "status": "pending",
        "challenge_complete": False,
        "handbrake": handbrake_str,
        "message": "Challenges are still pending resolution.",
        "pending": [k for k, v in CHALLENGES_RESOLVED.items() if not v]
    }

@app.get("/reset")
@app.post("/reset")
async def manual_reset():
    reset_all_challenges()
    return {
        "status": "success",
        "message": "Manual reset executed successfully! All challenges reverted to critical."
    }

# Gateway an FastAPI binden
gateway = FastAPIGateway(manager)
gateway.bind_to_app(app)

if __name__ == "__main__":
    import uvicorn
    # Wir nutzen Port 8010 fuer dieses Beispiel
    uvicorn.run(app, host="0.0.0.0", port=8010)
