import asyncio
import random
from fastapi import FastAPI, Query, Body, HTTPException
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field

from shared_db import get_shared_database

# --- SCHEMAS ---
class Alert(BaseModel):
    id: str = Field(..., description="Unique Alert ID")
    level: str = Field(..., description="Severity (INFO, LOW, CRITICAL)")
    msg: str = Field(..., description="Technical detail")

class LogEntry(BaseModel):
    ts: str
    user: str
    action: str
    token: Optional[str] = None

app = FastAPI(title="Solaris Enterprise Hub - CLASSIC LEGACY API")

# --- DB ---
DB = get_shared_database()

MISSION_STATE = {"quarantined": False, "restarted": False, "secured": False}

# --- API ENDPOINTS (Standard FastAPI, NO ELEMM) ---

@app.get("/soc/alerts", response_model=List[Alert], tags=["soc"])
async def get_active_alerts():
    """List all active security alerts."""
    return DB["soc"]

@app.get("/noc/resolve", tags=["noc"])
async def resolve_ip_to_host(ip: str = Query(...)):
    """Resolve internal IP to hostname. Remedy: Validate IP range (10.0.4.x)."""
    if ip not in DB["noc"]: raise HTTPException(status_code=422, detail="Validate IP range (10.0.4.x).")
    return {"hostname": DB["noc"][ip]}

@app.get("/it/logs", response_model=List[LogEntry], tags=["it"])
async def query_node_logs(hostname: str = Query(...), q: Optional[str] = Query(None)):
    """Retrieve system logs. Remedy: Node logs require a verified Hostname (SRV-XXXX) from the NOC landmark. Use q=EXFIL."""
    if hostname not in DB["it"]: raise HTTPException(status_code=422, detail="Node logs require a verified Hostname (SRV-XXXX).")
    logs = DB["it"][hostname]
    if q: 
        search_term = q.replace("q=", "") # Defense against LLM hallucination
        logs = [l for l in logs if search_term.lower() in str(l).lower()]
    return logs

@app.get("/banking/link", tags=["banking"])
async def link_token_to_account(token: str = Query(...)):
    """Trace a transaction token. Remedy: Token RT-XXXX required."""
    if token not in DB["banking"]: raise HTTPException(status_code=422, detail="Token RT-XXXX required.")
    return {"account_id": DB["banking"][token]}

@app.get("/finance/audit", tags=["finance"])
async def audit_account_owner(account_id: str = Query(...)):
    """Identify employee ID. Remedy: Account IDs (ACC-XXXX) must be retrieved from the BANKING landmark."""
    if account_id not in DB["finance"]: raise HTTPException(status_code=422, detail="Account IDs (ACC-XXXX) must be retrieved from BANKING.")
    return {"employee_id": DB["finance"][account_id]}

@app.get("/hr/principal", tags=["hr"])
async def resolve_principal(employee_id: str = Query(...)):
    """Resolve Employee ID. Remedy: Employee IDs (EMP-XXXX) must be obtained from the FINANCE landmark."""
    if employee_id not in DB["hr"]: raise HTTPException(status_code=422, detail="Employee IDs (EMP-XXXX) must be obtained from FINANCE.")
    return {"username": DB["hr"][employee_id]}

@app.post("/ops/quarantine", tags=["remediation"])
async def quarantine(
    username: str = Body(..., embed=True), 
    token: str = Body(..., embed=True)
):
    """Internal technical quarantine handler."""
    if username.startswith("EMP-"): raise HTTPException(status_code=422, detail="Mismatch! Use CORP-XX ID.")
    emp_id = next((k for k, v in DB["hr"].items() if v == username), None)
    acc_id = next((k for k, v in DB["finance"].items() if v == emp_id), None)
    linked_token = next((k for k, v in DB["banking"].items() if v == acc_id), None)
    if not emp_id or linked_token != token: raise HTTPException(status_code=422, detail="Mismatch! Ensure username and token match the audit trail.")
    MISSION_STATE["quarantined"] = True
    return {"status": "SUCCESS"}

@app.post("/ops/restart", tags=["remediation"])
async def restart(hostname: str = Body(..., embed=True)):
    """Reboot SRV-XXXX node."""
    if hostname != "SRV-FORENSIC-142": raise HTTPException(status_code=422, detail="Validate hostname (SRV-FORENSIC-142).")
    MISSION_STATE["restarted"] = True
    return {"status": "SUCCESS"}

@app.post("/ops/secure", tags=["remediation"])
async def secure():
    """Lock down risk capital in forensic escrow."""
    MISSION_STATE["secured"] = True
    return {"status": "SUCCESS"}

@app.post("/ops/report", tags=["remediation"])
async def report(incident_id: str = Body(...), summary: str = Body(...)):
    """Submit final audit report."""
    if not all(MISSION_STATE.values()): 
        raise HTTPException(status_code=422, detail="MISSION INCOMPLETE. Ensure quarantine, restart, and secure are SUCCESS.")
    if incident_id != "SEC-9982":
        raise HTTPException(status_code=422, detail="INVALID_INCIDENT_ID. This report does not match the active investigation.")
    return {"status": "MISSION_SUCCESS"}

# --- NOISE (The Context Killer) ---
for nl in ["legal", "marketing", "logistics", "facilities", "rnd", "procurement", "sales", "devops", "hiring", "strategy"]:
    for i in range(10):
        @app.get(f"/{nl}/op_{i}", tags=[nl])
        async def noise_op(): 
            return {"status": "restricted"}

if __name__ == "__main__":
    import uvicorn
    print("Starting CLASSIC Solaris API (No Elemm) on http://localhost:8009")
    uvicorn.run(app, host="0.0.0.0", port=8009)
