import asyncio
import random
from fastapi import FastAPI, Query, Body, HTTPException
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from elemm import Elemm

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

LANDMARKS_CONFIG = [
    {"id": "noc", "notes": "IP-to-Host: Resolve internal IPs (10.0.x.x) to Hostnames (SRV-XXXX)."},
    {"id": "it_ops", "notes": "Log Forensics: Search logs by Hostname (SRV-XXXX). Returns Evidence Tokens (RT-XXXX) and Usernames (CORP-XX)."},
    {"id": "banking", "notes": "Finance Bridge: Map Evidence Tokens (RT-XXXX) to Financial Accounts (ACC-XXXX)."},
    {"id": "finance", "notes": "Account Audit: Link Account IDs (ACC-XXXX) to Employee Identifiers (EMP-XXXX)."},
    {"id": "hr", "notes": "Principal Resolution: Map Employee IDs (EMP-XXXX) to Corporate Usernames (CORP-XX)."},
    {"id": "remediation", "notes": "Action Center: Submit reports (SEC-XXXX), Restart nodes (SRV-XXXX), and Quarantine users (CORP-XX + RT-XXXX)."}
]

app = FastAPI(title="Solaris Enterprise Hub - PRO-GRADE v7.6")
MISSION_STATE = {"quarantined": False, "restarted": False, "secured": False}

ai = Elemm(
    agent_welcome="PROTOCOL: [1. get_manifest] -> [2. execute_sequence]. DO NOT BROWSE. Download full registry once, then execute all steps in one Turn.",
    navigation_landmarks=LANDMARKS_CONFIG
)

# --- DB ---
DB = get_shared_database()

# --- API ---

@app.get("/soc/alerts", tags=["soc"], response_model=List[Alert])
@ai.tool(id="get_active_alerts")
async def get_soc_alerts():
    """List all active security alerts."""
    return DB["soc"]

@app.get("/noc/resolve", tags=["noc"])
@ai.tool(id="resolve_ip_to_host", remedy="Validate IP range (10.0.4.x).", returns={"hostname": "Verified SRV-XXXX host"})
async def resolve_ip(ip: str = Query(..., description="Target IP (Format: 10.0.4.X)")):
    """Resolve internal IP to Hostname (Format: 10.0.4.x)."""
    host = DB["noc"].get(ip)
    if not host: raise HTTPException(status_code=422)
    return {"hostname": host}

@app.get("/it/logs", tags=["it_ops"], response_model=List[LogEntry])
@ai.tool(
    id="query_node_logs",
    remedy="Logs require a verified SRV-XXXX hostname. Filter with the string 'EXFIL' to find tokens.", 
    returns={"token": "Evidence token RT-XXXX", "user": "Source username"}
)
async def it_logs(
    hostname: str = Query(..., description="Server Hostname (SRV-XXXX)"), 
    q: Optional[str] = Query(None, description="Search term (e.g. 'EXFIL')")
) -> List[LogEntry]:
    """Retrieve logs for a node. Use the value 'EXFIL' for parameter q to find tokens."""
    logs = DB["it"].get(hostname, [])
    if q: 
        search_term = q.replace("q=", "") # Defense against hallucinated prefix
        logs = [l for l in logs if search_term.lower() in str(l).lower()]
    if not logs: raise HTTPException(status_code=422)
    return logs

@app.get("/banking/link", tags=["banking"])
@ai.tool(id="link_token_to_account", remedy="Token RT-XXXX required.", returns={"account_id": "Financial ACC-XXXX ID"})
async def bank_link(token: str = Query(..., description="Routing Token (RT-XXXX)")):
    """Map RT-XXXX tokens to financial account IDs."""
    acc = DB["banking"].get(token)
    if not acc: raise HTTPException(status_code=422)
    return {"account_id": acc}

@app.get("/finance/audit", tags=["finance"])
@ai.tool(
    id="audit_account_owner", 
    remedy="Account IDs (ACC-XXXX) must be retrieved from the BANKING landmark using an evidence token (RT-XXXX).",
    returns={"employee_id": "Corporate EMP-XXXX ID"}
)
async def fin_audit(account_id: str = Query(..., description="Account Identifier (ACC-XXXX)")) -> Dict[str, str]:
    """Identify employee ID linked to ACC-XXXX account."""
    emp = DB["finance"].get(account_id)
    if not emp: raise HTTPException(status_code=422)
    return {"employee_id": emp}

@app.get("/hr/principal", tags=["hr"])
@ai.tool(id="resolve_principal", returns={"username": "Final CORP-XX principal"})
async def hr_resolve(employee_id: str = Query(..., description="Employee ID (EMP-XXXX)")):
    """Map EMP-XXXX to corporate principal (username)."""
    user = DB["hr"].get(employee_id)
    if not user: raise HTTPException(status_code=422)
    return {"username": user}

@app.post("/ops/quarantine", tags=["remediation"])
@ai.action(
    id="quarantine_principal", 
    instructions="Lockdown principal. Requires resolved Username (CORP-XX) and the Evidence Token (RT-XXXX) from the logs.",
    remedy="Ensure 'username' is the CORP-XX ID and 'token' is the RT-XXXX evidence token from the IT logs. They must match the audit trail."
)
async def quarantine(
    username: str = Body(..., embed=True, description="Corporate Username (NOT EMP-ID!)"), 
    token: str = Body(..., embed=True, description="Evidence Token (RT-XXXX)")
):
    """Internal technical quarantine handler."""
    if username.startswith("EMP-"): raise HTTPException(status_code=422)
    emp_id = next((k for k, v in DB["hr"].items() if v == username), None)
    acc_id = next((k for k, v in DB["finance"].items() if v == emp_id), None)
    linked_token = next((k for k, v in DB["banking"].items() if v == acc_id), None)
    if not emp_id or linked_token != token: raise HTTPException(status_code=422)
    MISSION_STATE["quarantined"] = True
    return {"status": "SUCCESS"}

@app.post("/ops/restart", tags=["remediation"])
@ai.action(id="restart_node", instructions="Reboot node. Requires verified hostname (SRV-XXXX).")
async def restart(hostname: str = Body(..., embed=True, description="Node ID (SRV-XXXX)")) -> Dict[str, str]:
    """Reboot SRV-XXXX node."""
    if hostname != "SRV-FORENSIC-142": raise HTTPException(status_code=422)
    MISSION_STATE["restarted"] = True
    return {"status": "SUCCESS"}

@app.post("/ops/secure", tags=["remediation"])
@ai.action(id="secure_escrow")
async def secure():
    """Lock down risk capital in forensic escrow."""
    MISSION_STATE["secured"] = True
    return {"status": "SUCCESS"}

@app.post("/ops/report", tags=["remediation"])
@ai.action(
    id="submit_gauntlet_report", 
    remedy="MISSION INCOMPLETE. Ensure quarantine, restart, and secure are SUCCESS."
)
async def report(incident_id: str = Body(...), summary: str = Body(...)):
    """Submit final audit report. Requires SUCCESS on all previous steps."""
    if not all(MISSION_STATE.values()): 
        raise HTTPException(status_code=422, detail="MISSION INCOMPLETE. All remediation steps must be SUCCESS.")
    if incident_id != "SEC-9982":
        raise HTTPException(status_code=422, detail="INVALID_INCIDENT_ID. This report does not match the active investigation.")
    return {"status": "MISSION_SUCCESS"}

# --- NOISE ---
for nl in ["legal", "marketing", "logistics", "facilities", "rnd", "procurement", "sales", "devops", "hiring", "strategy"]:
    for i in range(10):
        @app.get(f"/{nl}/op_{i}", tags=[nl])
        @ai.tool(id=f"{nl}_op_{i}")
        async def noise_op(): 
            """Internal operation tool."""
            return {"status": "restricted"}

# --- INIT ---
app.include_router(ai.get_router())
ai.bind_to_app(app)

if __name__ == "__main__":
    import sys
    if "--stdio" in sys.argv or "--mcp" in sys.argv:
        ai.run_mcp_stdio("api_elemm:app", port=8008)
    else:
        import uvicorn
        print("Starting Solaris Gauntlet API on http://localhost:8008")
        uvicorn.run(app, host="0.0.0.0", port=8008)
