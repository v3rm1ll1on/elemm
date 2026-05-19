import asyncio
import random
from fastapi import FastAPI, Query, Body, HTTPException
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field

from elemm import AIProtocolManager
from elemm.gateways.fastapi import FastAPIGateway
from shared_db import get_shared_database

# --- SCHEMAS ---
class Alert(BaseModel):
    id: str
    level: str
    msg: str

class LogEntry(BaseModel):
    ts: str
    user: str
    action: str
    token: Optional[str] = None

app = FastAPI(title="Solaris Enterprise Hub - V2 PROTOCOL")
MISSION_STATE = {"quarantined": False, "restarted": False, "secured": False}

LANDMARKS_CONFIG = [
    {"id": "noc", "notes": "IP-to-Host: Resolve internal IPs (10.0.x.x) to Hostnames (SRV-XXXX)."},
    {"id": "it_ops", "notes": "Log Forensics: Search logs by Hostname (SRV-XXXX). Returns Evidence Tokens (RT-XXXX) and Usernames (CORP-XX)."},
    {"id": "banking", "notes": "Finance Bridge: Map Evidence Tokens (RT-XXXX) to Financial Accounts (ACC-XXXX)."},
    {"id": "finance", "notes": "Account Audit: Link Account IDs (ACC-XXXX) to Employee Identifiers (EMP-XXXX)."},
    {"id": "hr", "notes": "Principal Resolution: Map Employee IDs (EMP-XXXX) to Corporate Usernames (CORP-XX)."},
    {"id": "remediation", "notes": "Action Center: Submit reports (SEC-XXXX), Restart nodes (SRV-XXXX), and Quarantine users (CORP-XX + RT-XXXX)."}
]

# --- MANAGER SETUP ---
manager = AIProtocolManager(
    instructions = """
You are an Autonomous Forensic Agent. 
MISSION: Resolve Incident SEC-9982 (Target IP: 10.0.4.142).
FORENSIC CHAIN:
1. noc:resolve_ip_to_host(ip='10.0.4.142') -> $host
2. it_ops:query_node_logs(hostname=$host.hostname, q='EXFIL') -> $logs
3. banking:link_token_to_account(token=$logs.evidence_token) -> $acc
4. finance:audit_account_owner(account_id=$acc.account_id) -> $emp
5. hr:resolve_principal(employee_id=$emp.employee_id) -> $user
6. remediation: quarantine, restart, escrow, and report.
    """.strip()
,
    version="2.0",
    navigation_landmarks=LANDMARKS_CONFIG,
    ctx_threshold=8192
)
manager.welcome_message = "WELCOME TO SOLARIS ENTERPRISE HUB (SECURED BY ELEMM v2)"
import os
metadata_path = os.path.join(os.path.dirname(__file__), "landmarks_v2.yaml")
manager.load_metadata(metadata_path)
gateway = FastAPIGateway(manager)

# --- DB ---
DB = get_shared_database()

# --- API ---

@app.get("/soc/alerts", tags=["soc"], response_model=List[Alert])
@manager.bind("soc:get_active_alerts")
async def get_soc_alerts():
    return DB["soc"]

@app.get("/noc/resolve", tags=["noc"])
@manager.bind("noc:resolve_ip_to_host")
async def resolve_ip(ip: str = Query(..., description="Target IP (Format: 10.0.4.X)")):
    host = DB["noc"].get(ip)
    if not host: raise HTTPException(status_code=422)
    return {"hostname": host}

@app.get("/it/logs", tags=["it_ops"], response_model=List[LogEntry])
@manager.bind("it_ops:query_node_logs")
async def it_logs(
    hostname: str = Query(..., description="Server Hostname (SRV-XXXX)"), 
    q: Optional[str] = Query(None, description="Search term (e.g. 'EXFIL')")
) -> List[LogEntry]:
    # Handle direct calls where q might still be the Query object
    search_term = None
    if q and isinstance(q, str):
        search_term = q.replace("q=", "").lower()
    elif q and hasattr(q, "default") and isinstance(q.default, str):
        search_term = q.default.replace("q=", "").lower()
    
    logs = DB["it"].get(hostname, [])
    if search_term: 
        logs = [l for l in logs if search_term in str(l).lower()]
        if not logs:
            return JSONResponse(
                status_code=422,
                content={"status": "error", "message": f"Keine Logs für Host '{hostname}' gefunden. Hast du den richtigen Hostname aus dem NOC-Tool?"}
            )  
    
    # Map 'token' to 'evidence_token' if necessary
    results = []
    for l in logs:
        entry = l.copy()
        if "token" in entry:
            entry["evidence_token"] = entry.pop("token")
        if "user" in entry:
            entry["username"] = entry.pop("user")
        results.append(entry)
    return results

@app.get("/banking/link", tags=["banking"])
@manager.bind("banking:link_token_to_account")
async def bank_link(token: str = Query(..., description="Routing Token (RT-XXXX)")):
    acc = DB["banking"].get(token)
    if not acc: 
        raise HTTPException(
            status_code=422, 
            detail=f"Token '{token}' konnte in der Banking-Datenbank nicht gefunden werden."
        )
    return {"account_id": acc, "token": token}

@app.get("/finance/audit", tags=["finance"])
@manager.bind("finance:audit_account_owner")
async def fin_audit(account_id: str = Query(..., description="Account Identifier (ACC-XXXX)")) -> Dict[str, str]:
    emp = DB["finance"].get(account_id)
    if not emp: 
        raise HTTPException(
            status_code=422, 
            detail=f"Konto-ID '{account_id}' existiert nicht in den Finanzunterlagen."
        )
    return {"employee_id": emp, "account_id": account_id}

@app.get("/hr/principal", tags=["hr"])
@manager.bind("hr:resolve_principal")
async def hr_resolve(employee_id: str = Query(..., description="Employee ID (EMP-XXXX)")):
    user = DB["hr"].get(employee_id)
    if not user: 
        raise HTTPException(
            status_code=422, 
            detail=f"Mitarbeiter-ID '{employee_id}' ist im HR-System unbekannt."
        )
    return {"username": user, "employee_id": employee_id}

@app.post("/ops/quarantine", tags=["remediation"])
@manager.bind("remediation:quarantine_principal")
async def quarantine(username: str, token: str):
    if username.startswith("EMP-"): raise HTTPException(status_code=422)
    emp_id = next((k for k, v in DB["hr"].items() if v == username), None)
    acc_id = next((k for k, v in DB["finance"].items() if v == emp_id), None)
    linked_token = next((k for k, v in DB["banking"].items() if v == acc_id), None)
    if not emp_id or linked_token != token: raise HTTPException(status_code=422)
    MISSION_STATE["quarantined"] = True
    return {"status": "SUCCESS"}

@app.post("/ops/restart", tags=["remediation"])
@manager.bind("remediation:restart_node")
async def restart(hostname: str) -> Dict[str, str]:
    if hostname != "SRV-FORENSIC-142": raise HTTPException(status_code=422)
    MISSION_STATE["restarted"] = True
    return {"status": "SUCCESS"}

@app.post("/ops/secure", tags=["remediation"])
@manager.bind("remediation:secure_escrow")
async def secure() -> Dict[str, str]:
    MISSION_STATE["secured"] = True
    return {"status": "SUCCESS"}

@app.post("/ops/report", tags=["remediation"])
@manager.bind("remediation:submit_gauntlet_report")
async def report(incident_id: str = Body(...), summary: str = Body(...)) -> Dict[str, str]:
    if not all(MISSION_STATE.values()): 
        raise HTTPException(status_code=422, detail="MISSION INCOMPLETE.")
    if incident_id != "SEC-9982":
        raise HTTPException(status_code=422, detail="INVALID_INCIDENT_ID.")
    return {"status": "MISSION_SUCCESS"}

# --- NOISE TOOLS (v1 Genius: Massive Tooling Simulation) ---
for nl in ["legal", "marketing", "logistics", "facilities", "rnd", "procurement", "sales", "devops", "hiring", "strategy"]:
    for i in range(10):
        endpoint = f"/{nl}/op_{i}"
        landmark_id = f"{nl}:op_{i}"
        
        @app.get(endpoint, tags=[nl])
        @manager.bind(landmark_id)
        async def noise_op():
            """Internal operation tool for administrative tasks."""
            return {"status": "restricted", "detail": "Access denied for current scope."}

gateway.bind_to_app(app)

if __name__ == "__main__":
    import sys
    if "--mcp" in sys.argv or "--stdio" in sys.argv:
        from elemm.gateways.mcp_server import MCPGateway
        mcp_gateway = MCPGateway(manager)
        mcp_gateway.run_stdio()
    else:
        import uvicorn
        print("Starting Solaris Gauntlet V2 on http://localhost:8008")
        uvicorn.run(app, host="0.0.0.0", port=8008)
