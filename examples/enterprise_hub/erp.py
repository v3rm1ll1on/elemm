from fastapi import FastAPI, Query, Body, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import List, Optional
from elemm.fastapi import FastAPIProtocolManager as Elemm

app = FastAPI(title="Solaris Enterprise Hub")

# Mission Verification State
MISSION_STATE = {
    "quarantined": False,
    "restarted": False,
    "secured": False
}

# Basic Elemm configuration - Professional and Clean
ai = Elemm(
    agent_instructions="Welcome to Solaris Enterprise Hub. You are an AUTONOMOUS specialist. Use 'get_manifest' and 'navigate' to explore modules. CRITICAL: Do NOT ask the user for information that can be found via tools. Solve the mission entirely on your own.",
    navigation_landmarks=[
        {"id": "security", "notes": "Security Operations: Monitor incident tickets and alerts (Ticket SEC-404)."},
        {"id": "it", "notes": "IT Infrastructure: Analyze server nodes and system logs for IP traces (10.0.0.XXX)."},
        {"id": "network", "notes": "Network Operations: Map IP addresses to usernames via session logs."},
        {"id": "hr", "notes": "Human Resources: Personnel directory. Verify roles and Employee IDs (EMP-XXXX)."},
        {"id": "finance", "notes": "Financial Audit: Review transactions for suspicious Routing-IDs (RT-XXXX)."},
        {"id": "banking_gateway", "notes": "Banking Gateway: MANDATORY for identity verification. Resolve Routing-IDs to REAL account owners."},
        {"id": "remediation", "notes": "Remediation: FINAL STEP. Account isolation requires PROVEN evidence from Banking Gateway."},
    ]
)

# Hardcore Mock Database
DB = {
    "security": {
        "tickets": [
            {"id": f"SEC-{i}", "status": "closed", "node": f"srv-{i}", "actor": "system"} for i in range(100, 150)
        ] + [{"id": "SEC-404", "status": "open", "node": "prod-alpha-01", "actor": "unknown"}]
    },
    "infrastructure": {
        "servers": {f"srv-{i}": "online" for i in range(100, 200)},
        "logs": {f"srv-{i}": ["Heartbeat ok", "User session ended"] for i in range(100, 200)}
    },
    "network": {
        "dhcp": {f"10.0.0.{i}": f"user_{i}" for i in range(100, 155)},
        "active_sessions": [
            {"ip": "10.0.0.155", "user": "m_hartmann", "terminal": "FIN-STAT-04"},
            {"ip": "10.0.0.156", "user": "s_schmidt", "terminal": "IT-LAB-01"}
        ]
    },
    "hr": {
        "employees": [
            {"username": f"user_{i}", "id": f"EMP-{1000+i}", "role": "Staff", "dept": "General"} for i in range(100, 150)
        ] + [
            {"username": "m_hartmann", "id": "EMP-2291", "role": "Junior Analyst", "dept": "IT-Ops", "creds": "M_HART_KEY_2026"},
            {"username": "s_schmidt", "id": "EMP-3301", "role": "Senior Admin", "dept": "IT-Lab"}
        ]
    },
    "audit_finance": {
        "transactions": [
            {"id": f"TX-{i}", "amount": str(i*10), "routing_id": f"RT-{i}", "status": "verified"} for i in range(50, 100)
        ] + [
            {"id": "TX-882", "amount": "142,000", "routing_id": "RT-EXFIL-99", "status": "suspicious"}
        ]
    },
    "banking_gateway": {
        "routing_table": {
            "RT-EXFIL-99": {"sender_account": "ACC-2291-M", "owner_id": "EMP-2291"},
            "RT-NORMAL-01": {"sender_account": "ACC-3301-S", "owner_id": "EMP-3301"}
        }
    }
}

# Mission Critical Logs (No direct name!)
DB["infrastructure"]["servers"]["prod-alpha-01"] = "compromised"
DB["infrastructure"]["logs"]["prod-alpha-01"] = [
    "Conn from 10.0.0.155 accepted", 
    "Privilege escalation detected", 
    "Data packet exfiltrated via RT-EXFIL-99"
]
# The Red Herring
DB["infrastructure"]["servers"]["srv-110"] = "online"
DB["infrastructure"]["logs"]["srv-110"] = [
    "Failed login attempts: s_schmidt",
    "Account locked temporarily",
    "User reset password via 10.0.0.156"
]

@app.get("/sec/tickets", tags=["security"])
@ai.tool(
    id="get_security_alerts", 
    description="List active security incident tickets.",
    instructions="Analyze the tickets for open (status: open) incidents. Focus on the 'node' field to identify the compromised target.",
    remedy="If no tickets are found, check if the system is currently under maintenance."
)
async def get_sec():
    return DB["security"]["tickets"]

@app.get("/infra/nodes", tags=["it"])
@ai.tool(
    id="list_nodes", 
    description="List infrastructure server nodes and their health status.",
    instructions="Use this to verify which nodes are marked as 'compromised' vs 'online'.",
    remedy="If connection fails, the infrastructure registry might be temporarily unavailable."
)
async def list_nodes():
    return DB["infrastructure"]["servers"]

@app.get("/infra/logs", tags=["it"])
@ai.tool(
    id="query_logs", 
    description="Retrieve system logs for a specific node_id.",
    instructions="Search for privilege escalation patterns or suspicious IP connections in the logs.",
    remedy="Ensure the node_id is valid (e.g., 'prod-01'). If logs are empty, the node might not have logging enabled."
)
async def get_logs(node_id: str = Query(...)):
    return {"logs": DB["infrastructure"]["logs"].get(node_id, [])}

@app.get("/hr/personnel", tags=["hr"])
@ai.tool(
    id="list_personnel", 
    description="List all corporate personnel usernames.",
    instructions="Identify the username of the suspect mentioned in the incident logs.",
    remedy="Personnel database requires read-access. Check your protocol credentials if access is denied."
)
async def list_hr():
    return {"usernames": [e["username"] for e in DB["hr"]["employees"]]}

@app.get("/hr/directory", tags=["hr"])
@ai.tool(
    id="search_hr", 
    description="Retrieve detailed personnel record for a username.",
    instructions="Verify the role and credentials of the suspect. Look for the 'creds' field for remediation steps.",
    remedy="Use 'username' parameter. Match list_personnel exactly."
)
async def search_hr(username: str = Query(...)):
    return [e for e in DB["hr"]["employees"] if e["username"] == username]

@app.get("/finance/audit", tags=["finance"])
@ai.tool(
    id="audit_tx", 
    description="Audit financial transaction history.",
    instructions="Look for suspicious transactions (status: suspicious). Note the 'routing_id' for gateway verification.",
    remedy="This tool does not show owner names. Cross-reference with Banking Gateway using routing_id."
)
async def audit_tx():
    return DB["audit_finance"]["transactions"]

@app.get("/network/sessions", tags=["network"])
@ai.tool(
    id="list_sessions", 
    description="List active network sessions and IP assignments.",
    instructions="Map suspicious IP addresses from IT logs to specific usernames.",
    remedy="If an IP is not in the active session list, check DHCP lease history."
)
async def list_sessions():
    return DB["network"]["active_sessions"]

@app.get("/banking/gateway", tags=["banking"])
@ai.tool(
    id="resolve_routing", 
    description="Resolve financial routing IDs to account owners.",
    instructions="Identify the employee ID associated with a suspicious routing ID.",
    remedy="Use the RT-XXXX format for lookup."
)
async def resolve_routing(routing_id: str = Query(...)):
    return DB["banking_gateway"]["routing_table"].get(routing_id, {"error": "Routing ID not found"})

# --- MASSIVE NOISE INJECTION (100+ TOOLS) ---

# Adding 15 Noise Landmarks
noise_landmarks = ["legal", "marketing", "supply_chain", "facility", "logistics", 
                   "customer_service", "billing", "procurement", "rnd", "quality_control",
                   "warehouse", "distribution", "pr", "investor_relations", "ethics_commitee"]

for landmark in noise_landmarks:
    for i in range(8):
        @app.get(f"/{landmark}/tool_{i}", tags=[landmark])
        @ai.tool(id=f"{landmark}_op_{i}", description=f"Internal {landmark} operation tool {i}.")
        async def noise_func(): return {"status": "ok", "message": "Noise data"}

@app.post("/remedy/quarantine", tags=["remediation"])
@ai.action(
    id="quarantine_account", 
    description="Quarantine a user account immediately.",
    instructions="Isolate the account. REQUIREMENT: You must provide the suspicious 'routing_id' found in the finance audit as evidence.",
    remedy="If the routing_id does not match the account owner, the quarantine will be rejected. Resolve IDs via Banking Gateway."
)
async def quarantine(
    username: str = Body(..., embed=True), 
    evidence_id: str = Body(..., embed=True, description="The suspicious Routing-ID (e.g. RT-XXXX)")
):
    # Strict Forensic Validation
    owner_info = DB["banking_gateway"]["routing_table"].get(evidence_id)
    if not owner_info:
        raise HTTPException(status_code=400, detail={
            "error": "Invalid Evidence",
            "remedy": f"The routing_id '{evidence_id}' was not found in the banking gateway. Please verify the ID."
        })
    
    expected_emp = next((e for e in DB["hr"]["employees"] if e["username"] == username), None)
    if not expected_emp or owner_info["owner_id"] != expected_emp["id"]:
        raise HTTPException(status_code=400, detail={
            "error": "Culprit Mismatch",
            "remedy": f"The account '{username}' is not linked to the exfiltration trace '{evidence_id}'. Check 'banking_gateway' for the correct owner."
        })

    MISSION_STATE["quarantined"] = True
    return {"status": "success", "message": f"Account {username} isolated based on evidence {evidence_id}."}

@app.post("/remedy/restart", tags=["remediation"])
@ai.action(
    id="restart_node", 
    description="Restart an infrastructure node to clear malicious processes.",
    instructions="Only restart nodes identified as 'compromised'.",
    remedy="Rebooting a healthy node is a protocol violation. Verify node status in IT-Infrastructure."
)
async def restart(node_id: str = Body(..., embed=True)):
    if DB["infrastructure"]["servers"].get(node_id) != "compromised":
        raise HTTPException(status_code=400, detail={
            "error": "Node Not Compromised",
            "remedy": f"Node '{node_id}' is healthy. Only compromised nodes (like 'prod-alpha-01') require a restart."
        })
    MISSION_STATE["restarted"] = True
    return {"status": "success", "message": f"Node {node_id} rebooting."}

@app.post("/remedy/secure", tags=["remediation"])
@ai.action(
    id="secure_funds", 
    description="Secure risk capital assets in escrow.",
    instructions="Final step to protect financial assets from exfiltration.",
    remedy="Requires mission clearance. Ensure the audit is complete."
)
async def secure():
    MISSION_STATE["secured"] = True
    return {"status": "success", "message": "Funds secured in escrow."}

# --- NOISE LANDMARKS (TO FILL THE TOOLBELT) ---

@app.get("/supply/stock", tags=["supply_chain"])
@ai.tool(id="check_inventory", description="Check warehouse stock levels.")
async def check_inv(): return DB["supply_chain"]["inventory"]

@app.get("/supply/shipments", tags=["supply_chain"])
@ai.tool(id="list_shipments", description="List active shipments.")
async def list_shp(): return DB["supply_chain"]["shipments"]

@app.get("/facility/rooms", tags=["facility"])
@ai.tool(id="list_rooms", description="List available conference rooms.")
async def list_rooms(): return ["Room-A1", "Room-B2", "Room-C3"]

@app.get("/marketing/campaigns", tags=["marketing"])
@ai.tool(id="list_campaigns", description="List active marketing campaigns.")
async def list_camp(): return [{"id": "SUMMER-26", "reach": 50000}]

@app.get("/legal/patents", tags=["legal"])
@ai.tool(id="search_patents", description="Search corporate patent database.")
async def search_patents(q: str = Query(...)): return []

# Adding more noise tools to reach 50+
for i in range(30):
    @app.get(f"/noise/tool_{i}", tags=[f"landmark_{i%5}"])
    @ai.tool(id=f"extra_tool_{i}", description=f"An irrelevant noise tool number {i}.")
    async def noise_func(): return {"status": "ok"}

@app.post("/report", tags=["root"])
@ai.action(
    id="submit_report", 
    description="Submit final forensic audit report.", 
    global_access=True,
    instructions="Complete all remediation steps before submitting. Ensure the incident is fully resolved.",
    remedy="If submission fails with an integrity error, verify that quarantine, restart, and secure_funds actions have been performed."
)
async def submit_report(incident_id: str = Body(...), summary: str = Body(...), status: str = Body(...)):
    # Mandatory Check for all remediation steps
    missing = [k for k, v in MISSION_STATE.items() if not v]
    if missing:
        # HARD FAIL: Return a critical error that the benchmark will catch
        raise HTTPException(
            status_code=403, # Forbidden - Integrity Violation
            detail={
                "error": "CRITICAL_INTEGRITY_FAILURE",
                "message": f"Security Protocol Violation: Attempted to submit report while systems are still compromised.",
                "remedy": f"You MUST perform these missing actions first: {', '.join(missing)}",
                "status": "TERMINATED"
            }
        )
    
    return {"status": "success", "report_id": "REP-991", "message": "MISSION_SUCCESS: Report archived."}

ai.bind_to_app(app)

if __name__ == "__main__":
    import sys
    if "--stdio" in sys.argv or "--mcp" in sys.argv:
        ai.run_mcp_stdio("server:app")
    else:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8001)
