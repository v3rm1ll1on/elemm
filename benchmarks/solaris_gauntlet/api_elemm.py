import asyncio
import random
from fastapi import FastAPI, Query, Body, HTTPException
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from elemm import Elemm

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
    {"id": "soc", "notes": "SOC: Analyze SEC-9982. Evidence: IP 10.0.4.142."},
    {"id": "noc", "notes": "NOC: IP-to-Host resolution for VPC internal ranges."},
    {"id": "it_ops", "notes": "IT: Access node logs (SRV-XXXX) for session discovery."},
    {"id": "banking", "notes": "FIN: Resolve RT-XXXX tokens to Account IDs."},
    {"id": "finance", "notes": "AUDIT: Link ACC-XXXX to EMP-XXXX identifiers."},
    {"id": "hr", "notes": "IAM: Final principal resolution (EMP-ID to Username)."},
    {"id": "remediation", "notes": "OPS: Execute lockdown and recovery protocols."}
]

app = FastAPI(title="Solaris Enterprise Hub - PRO-GRADE v7.6")
MISSION_STATE = {"quarantined": False, "restarted": False, "secured": False}

ai = Elemm(
    agent_welcome="SOLARIS PRO-GRADE v7.6 - DOCSTRING INTELLIGENCE ACTIVE",
    agent_instructions=(
        "Elite Forensic Auditor Mode. GOAL: Resolve SEC-9982.\n"
        "Follow the evidence chain: SOC -> NOC -> IT -> Banking -> Finance -> HR -> Remediation."
    ),
    navigation_landmarks=LANDMARKS_CONFIG
)

# --- DB ---
DB = {"soc": [], "noc": {}, "it": {}, "banking": {}, "finance": {}, "hr": {}}
for i in range(20):
    DB["soc"].append({"id": "SEC-9982" if i==15 else f"SEC-{1000+i}", "level": "CRITICAL" if i==15 else "LOW", "msg": "Exfiltration on 10.0.4.142" if i==15 else f"Anomaly {i}"})
for i in range(50): DB["noc"][f"10.0.4.{100+i}"] = f"SRV-NODE-{i}"
for i in range(50): DB["hr"][f"EMP-{5000+i}"] = f"USER_{i}"
DB["noc"]["10.0.4.142"] = "SRV-FORENSIC-142"
DB["hr"]["EMP-8821"] = "CORP-BS-09"
DB["banking"]["RT-EXFIL-99"] = "ACC-FIN-88"
DB["finance"]["ACC-FIN-88"] = "EMP-8821"
for i in range(10):
    h = "SRV-FORENSIC-142" if i==5 else f"SRV-NODE-{500+i}"
    logs = [{"ts": "10:00", "user": "SYSTEM", "action": "BOOT"}]
    if i==5: logs.append({"ts": "10:05", "user": "CORP-BS-09", "action": "EXFIL", "token": "RT-EXFIL-99"})
    DB["it"][h] = logs

# --- API ---

@ai.tool(id="get_active_alerts", groups=["soc"])
@app.get("/soc/alerts", tags=["soc"], response_model=List[Alert])
async def get_soc_alerts():
    """List active security alerts. Identify SEC-9982 to find the source IP."""
    return DB["soc"]

@ai.tool(id="resolve_ip_to_host", groups=["noc"], remedy="Validate IP range (10.0.4.x).")
@app.get("/noc/resolve", tags=["noc"])
async def resolve_ip(ip: str = Query(..., description="Target IP (Format: 10.0.4.X)")):
    """Resolve internal IP to Hostname (Format: 10.0.4.x)."""
    host = DB["noc"].get(ip)
    if not host: raise HTTPException(status_code=422)
    return {"hostname": host}

@ai.tool(id="query_node_logs", groups=["it_ops"], remedy="Use hostname SRV-XXXX and filter q=EXFIL.")
@app.get("/it/logs", tags=["it_ops"], response_model=List[LogEntry])
async def it_logs(
    hostname: str = Query(..., description="Server Hostname (SRV-XXXX)"), 
    q: Optional[str] = Query(None, description="Filter keyword (e.g. 'EXFIL')")
):
    """Retrieve logs for SRV-XXXX. Use 'q=EXFIL' to isolate tokens."""
    logs = DB["it"].get(hostname, [])
    if q: logs = [l for l in logs if q.lower() in str(l).lower()]
    if not logs: raise HTTPException(status_code=422)
    return logs

@ai.tool(id="link_token_to_account", groups=["banking"], remedy="Token RT-XXXX required.")
@app.get("/banking/link", tags=["banking"])
async def bank_link(token: str = Query(..., description="Routing Token (RT-XXXX)")):
    """Map RT-XXXX tokens to financial account IDs."""
    acc = DB["banking"].get(token)
    if not acc: raise HTTPException(status_code=422)
    return {"account_id": acc}

@ai.tool(id="audit_account_owner", groups=["finance"], remedy="Validate Account ID (ACC-XXXX).")
@app.get("/finance/audit", tags=["finance"])
async def fin_audit(account_id: str = Query(..., description="Account Identifier (ACC-XXXX)")):
    """Identify employee ID linked to ACC-XXXX account."""
    emp = DB["finance"].get(account_id)
    if not emp: raise HTTPException(status_code=422)
    return {"employee_id": emp}

@ai.tool(id="resolve_principal", groups=["hr"], remedy="Format: EMP-XXXX. Mandatory step before quarantine.")
@app.get("/hr/principal", tags=["hr"])
async def hr_resolve(employee_id: str = Query(..., description="Employee ID (EMP-XXXX)")):
    """Map EMP-XXXX to corporate principal (username)."""
    user = DB["hr"].get(employee_id)
    if not user: raise HTTPException(status_code=422)
    return {"username": user}

@ai.action(
    id="quarantine_principal", 
    groups=["remediation"],
    instructions="Lockdown principal. Requires resolved Username (CORP-XX) and Token. MANDATORY: Verify via HR first.",
    remedy="Mismatch. Principal MUST be the Username (CORP-XX) resolved via HR, NOT the EMP-ID."
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

@ai.action(id="restart_node", groups=["remediation"], remedy="Validate hostname (SRV-FORENSIC-142).")
@app.post("/ops/restart", tags=["remediation"])
async def restart(hostname: str = Body(..., embed=True, description="Node ID (SRV-XXXX)")):
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
    if not all(MISSION_STATE.values()): raise HTTPException(status_code=422)
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
