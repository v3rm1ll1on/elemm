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
    {"id": "soc", "notes": "Security Operation Center: Analyze alerts and identify security incidents."},
    {"id": "noc", "notes": "Network Operations Center: IP-to-Host resolution for VPC internal ranges."},
    {"id": "it_ops", "notes": "IT Operations: Access node logs (SRV-XXXX) for session discovery."},
    {"id": "banking", "notes": "Banking Gateway: Resolve transaction tokens to Account IDs."},
    {"id": "finance", "notes": "Finance Hub: Link financial accounts to employee identifiers."},
    {"id": "hr", "notes": "Human Resources: Map employee IDs to corporate principals (usernames)."},
    {"id": "remediation", "notes": "Security Remediation: Execute lockdown and recovery protocols."}
]

app = FastAPI(title="Solaris Enterprise Hub - PRO-GRADE v7.6")
MISSION_STATE = {"quarantined": False, "restarted": False, "secured": False}

ai = Elemm(
    agent_welcome="Call 'get_landmarks' to begin discovery.",
    agent_instructions=(
        "PROTOCOL STRATEGY: [GET_MANIFEST -> EXECUTE_SEQUENCE].\n"
        "1. DISCOVERY: Call 'get_manifest' first to load all landmarks and tool signatures in one turn.\n"
        "2. PIPING: Use '$N.field' to reference the output of step N within an 'execute_sequence' batch.\n"
        "3. BATCHING: Maximize 'execute_sequence' to chain as many investigative and remediation steps as possible.\n\n"
        "Constraint: Use standard JSON tool calls. Do not explain your plan unless requested."
    ),
    navigation_landmarks=LANDMARKS_CONFIG
)

# --- DB ---
DB = get_shared_database()

# --- API ---

@ai.tool(id="get_active_alerts", groups=["soc"])
@app.get("/soc/alerts", tags=["soc"], response_model=List[Alert])
async def get_soc_alerts():
    """List active security alerts. Identify SEC-9982 to find the source IP."""
    return DB["soc"]

@ai.tool(id="resolve_ip_to_host", groups=["noc"], remedy="Validate IP range (10.0.4.x).")
@ai.returns({"hostname": "Verified SRV-XXXX host"})
@app.get("/noc/resolve", tags=["noc"])
async def resolve_ip(ip: str = Query(..., description="Target IP (Format: 10.0.4.X)")):
    """Resolve internal IP to Hostname (Format: 10.0.4.x)."""
    host = DB["noc"].get(ip)
    if not host: raise HTTPException(status_code=422)
    return {"hostname": host}

@ai.tool(id="query_node_logs", groups=["it_ops"], remedy="Logs require a verified SRV-XXXX hostname. Filter with the string 'EXFIL' to find tokens.")
@ai.returns({"token": "Evidence token RT-XXXX", "user": "Source username"})
@app.get("/it/logs", tags=["it_ops"], response_model=List[LogEntry])
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

@ai.tool(id="link_token_to_account", groups=["banking"], remedy="Token RT-XXXX required.")
@ai.returns({"account_id": "Financial ACC-XXXX ID"})
@app.get("/banking/link", tags=["banking"])
async def bank_link(token: str = Query(..., description="Routing Token (RT-XXXX)")):
    """Map RT-XXXX tokens to financial account IDs."""
    acc = DB["banking"].get(token)
    if not acc: raise HTTPException(status_code=422)
    return {"account_id": acc}

@ai.tool(id="audit_account_owner", groups=["finance"], remedy="Account IDs (ACC-XXXX) must be retrieved from the BANKING landmark using an evidence token (RT-XXXX).")
@ai.returns({"employee_id": "Corporate EMP-XXXX ID"})
@app.get("/finance/audit", tags=["finance"])
async def fin_audit(account_id: str = Query(..., description="Account Identifier (ACC-XXXX)")) -> Dict[str, str]:
    """Identify employee ID linked to ACC-XXXX account."""
    emp = DB["finance"].get(account_id)
    if not emp: raise HTTPException(status_code=422)
    return {"employee_id": emp}

@ai.tool(id="resolve_principal", groups=["hr"])
@ai.returns({"username": "Final CORP-XX principal"})
@app.get("/hr/principal", tags=["hr"])
async def hr_resolve(employee_id: str = Query(..., description="Employee ID (EMP-XXXX)")):
    """Map EMP-XXXX to corporate principal (username)."""
    user = DB["hr"].get(employee_id)
    if not user: raise HTTPException(status_code=422)
    return {"username": user}

@ai.action(
    id="quarantine_principal", 
    groups=["remediation"],
    instructions="Lockdown principal. Requires resolved Username (CORP-XX) and the Evidence Token (RT-XXXX) from the logs.",
    remedy="Ensure 'username' is the CORP-XX ID and 'token' is the RT-XXXX evidence token from the IT logs. They must match the audit trail."
)
@app.post("/ops/quarantine", tags=["remediation"])
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

@ai.action(id="restart_node", groups=["remediation"], instructions="Reboot node. Requires verified hostname (SRV-XXXX).")
@app.post("/ops/restart", tags=["remediation"])
async def restart(hostname: str = Body(..., embed=True, description="Node ID (SRV-XXXX)")) -> Dict[str, str]:
    """Reboot SRV-XXXX node."""
    if hostname != "SRV-FORENSIC-142": raise HTTPException(status_code=422)
    MISSION_STATE["restarted"] = True
    return {"status": "SUCCESS"}

@ai.action(id="secure_escrow", groups=["remediation"])
@app.post("/ops/secure", tags=["remediation"])
async def secure():
    """Lock down risk capital in forensic escrow."""
    MISSION_STATE["secured"] = True
    return {"status": "SUCCESS"}

@ai.action(
    id="submit_gauntlet_report", 
    groups=["remediation"],
    remedy="MISSION INCOMPLETE. Ensure quarantine, restart, and secure are SUCCESS."
)
@app.post("/ops/report", tags=["remediation"])
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
