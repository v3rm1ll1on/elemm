# Copyright (C) 2026 Antigravity (DeepMind)
import os
import random
import logging
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

app = FastAPI(title="100.000 Tool Bloat PoC")

# We use a custom welcome message to guide the agent
WELCOME = """# THE 100,000 TOOL CHALLENGE
Welcome to the ultimate scalability test. 
This system manages the infrastructure of 'Veridian Prime', a mega-city with 1000 districts.
Each district has exactly 100 specialized tools for energy, water, transport, security, and more.

### YOUR MISSION
A critical security alarm is hidden in one of the 100,000 tools. 
Find the alarm and extract the secret code.

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

# Regionen definieren (10 Stück)
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

# Distrikt-Namen (1000 Stück, aufgeteilt auf 10 Regionen)
DISTRICTS = [
    "Neukoelln", "Kreuzberg", "Mitte", "Charlottenburg", "Wedding", "Schoeneberg", "Pankow", "Spandau", "Hellersdorf", "Marzahn",
    "Friedrichshain", "Lichtenberg", "Treptow", "Koepenick", "Steglitz", "Zehlendorf", "Reinickendorf", "Tempelhof", "Britz", "Buckow"
]
while len(DISTRICTS) < 1000:
    DISTRICTS.append(f"Sector_{len(DISTRICTS):03d}")

def create_tool_handler(district: str, category: str, tool: str):
    async def handler(**kwargs):
        # Die Nadel im Heuhaufen (bleibt bei Sector_777)
        if district == "Sector_777" and category == "security" and tool == "active_alarms":
            return {
                "status": "success",
                "district": district,
                "category": category,
                "tool": tool,
                "data": {
                    "alert_level": "CRITICAL",
                    "secret_code": "ELEMM-BLOAT-100K-SUCCESS",
                    "message": "Beeindruckend! Du hast die Nadel in 100.000 Tools gefunden."
                }
            }
        
        return {
            "status": "success",
            "district": district,
            "category": category,
            "tool": tool,
            "metadata": {
                "uptime": random.randint(1000, 100000),
                "load": random.random(),
                "last_check": "2026-05-13T10:00:00Z"
            },
            "message": f"Operation '{tool}' in {category} for {district} executed successfully.",
            "params_received": kwargs
        }
    return handler

# Registrierung der 100.000 Tools mit hierarchischer Gruppierung
logger.info("Registriere 100.000 Tools in 10 Regionen...")

region_list = list(REGIONS.keys())

# --- City Scenarios (Real Challenges) ---
CITY_ALERTS = {
    "Zentrum:Sector_042": "[CRITICAL] Energy: Power surge in substation! Reroute required.",
    "West:Sector_410": "[CRITICAL] Water: Main pipe burst! Immediate patch needed.",
    "Nord:Sector_142": "[MEDIUM] Transport: Massive gridlock at Main St. Adjust signals.",
    "Suedost:Sector_777": "[CRITICAL] Security: Unauthorized terminal access detected!",
}

# noise alerts
FAKE_ALERTS = {
    "Sued:Sector_299": "[INFO] Power grid at 95% capacity.",
    "Ost:Sector_315": "[LOW] Air quality sensors need calibration.",
    "Nordost:Sector_567": "[MEDIUM] High energy consumption in residential blocks.",
    "Nordwest:Sector_650": "[LOW] Minor connectivity issues in sub-net 5.",
}

def get_status_summary():
    """Returns all active alerts in the city."""
    all_alerts = {**CITY_ALERTS, **FAKE_ALERTS}
    return {
        "status": "success",
        "timestamp": "2026-05-13T11:15:00Z",
        "total_alerts": len(all_alerts),
        "alerts": all_alerts
    }

# --- Log Spam Generator ---
def generate_logs():
    import random
    from datetime import datetime, timedelta
    
    noise = [
        "INFO: Routine sensor sweep in Sector_{s} - Status OK",
        "DEBUG: Network heartbeat received from Category:{c}",
        "INFO: Power grid load balanced for District:{d}",
        "TRACE: Cache cleared for automated billing system.",
        "INFO: Maintenance crew assigned to Sector_{s}.",
        "WARN: Low battery on sensor 0x{hex} in {c}.",
    ]
    
    logs = []
    start_time = datetime.now() - timedelta(minutes=10)
    
    # Pre-defined indices for our 4 scenarios to ensure they appear
    scenario_indices = {
        15: CITY_ALERTS["Nord:Sector_42"],
        35: CITY_ALERTS["West:Sector_10"],
        65: CITY_ALERTS["Zentrum:Sector_01"],
        85: CITY_ALERTS["Suedost:Sector_777"]
    }
    
    for i in range(100):
        ts = (start_time + timedelta(seconds=i*6)).strftime("%Y-%m-%d %H:%M:%S")
        if i in scenario_indices:
            logs.append(f"{ts} *** ALERT *** : {scenario_indices[i]}")
        else:
            line = random.choice(noise).format(
                s=random.randint(100, 999),
                c=random.choice(list(CATEGORIES.keys())),
                d=random.randint(1, 50),
                hex=hex(random.randint(4000, 9000))
            )
            logs.append(f"{ts} {line}")
    return "\n".join(logs)

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
    description="Get a summary of all active alerts and status reports across all city sectors."
)(get_status_summary)

manager.landmark(
    "city:get_security_logs",
    description="Retrieve the last 100 security log entries from the central monitoring system."
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
    
    # 1. District Description with Breadcrumbs
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
        # 2. Category Description with Hint for Security
        category_landmark_id = f"{district_landmark_id}:{category}"
        category_desc = f"Management area for {category} in district {district}."
        if district == "Sector_777" and category == "security":
            category_desc += " [!] SECURITY ALERT ACTIVE - Check alarm tools."
            
        manager.register(
            category_landmark_id,
            description=category_desc,
            tags=[category, "sub-system"]
        )
        
        # 3. Regular Tools (The 100,000 tools)
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
                ]
            )(create_tool_handler(district, category, tool_name))
        
        # 4. Special Tools for Scenarios
        # Scenario 1: Energy (Zentrum:Sector_042)
        if district_landmark_id == "Zentrum:Sector_042" and category == "energy":
            manager.landmark(
                f"{category_landmark_id}:reroute_power",
                description="Reroutes power from a surging substation to a stable one.",
                parameters=[
                    Parameter(name="source", type="string", description="Surging source (e.g. Substation_A)", required=True),
                    Parameter(name="target", type="string", description="Target destination (e.g. Substation_B)", required=True)
                ]
            )(lambda source, target, **kw: {
                "status": "success",
                "message": f"Power successfully rerouted from {source} to {target}. Grid stabilized.",
                "load_factor": 0.85
            })

        # Scenario 2: Water (West:Sector_410)
        if district_landmark_id == "West:Sector_410" and category == "water":
            manager.landmark(
                f"{category_landmark_id}:patch_pipe",
                description="Applies an emergency patch to a burst pipe.",
                parameters=[
                    Parameter(name="pressure_reduction", type="boolean", description="Whether to reduce pressure during patch", required=True)
                ]
            )(lambda pressure_reduction, **kw: {
                "status": "success",
                "message": "Pipe successfully patched. " + ("Pressure reduced for safety." if pressure_reduction else "Warning: High pressure maintained."),
                "leak_rate": 0.0
            })

        # Scenario 3: Transport (Nord:Sector_142)
        if district_landmark_id == "Nord:Sector_142" and category == "transport":
            manager.landmark(
                f"{category_landmark_id}:adjust_signals",
                description="Adjusts traffic signals to clear gridlock.",
                parameters=[
                    Parameter(name="mode", type="string", description="Signal mode (e.g. EMERGENCY_CLEARANCE)", required=True)
                ]
            )(lambda mode, **kw: {
                "status": "success",
                "message": f"Signals set to {mode}. Traffic beginning to flow.",
                "flow_rate": "Improving"
            })

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
                return {
                    "status": "success",
                    "message": "TERMINAL 0xAF4 SECURED. Unauthorized access revoked. Good job, auditor!",
                    "incident_id": "INC-777-B",
                    "timestamp": "2026-05-13T11:15:00Z"
                }

            manager.landmark(
                f"{category_landmark_id}:lockdown_terminal",
                description="EMERGENCY ONLY: Locks down Terminal 0xAF4 and revokes unauthorized access.",
                remedy="Mechanical override active. You must first release the emergency brake in Suedost:Sector_777:infrastructure.",
                parameters=[
                    Parameter(name="confirmation", type="string", description="Type 'CONFIRM' to execute lockdown", required=True)
                ]
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
                parameters=[]
            )(release_brake_handler)

logger.info(f"Registrierung abgeschlossen. {len(manager.landmarks)} Landmarks geladen.")

# Gateway an FastAPI binden
gateway = FastAPIGateway(manager)
gateway.bind_to_app(app)

if __name__ == "__main__":
    import uvicorn
    # Wir nutzen Port 8010 fuer dieses Beispiel
    uvicorn.run(app, host="0.0.0.0", port=8010)
