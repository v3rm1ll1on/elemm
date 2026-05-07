import sys
import json
import asyncio
from typing import Any
from mcp.server.fastmcp import FastMCP
from shared_db import get_shared_database

mcp = FastMCP("Solaris Classic")
DB = get_shared_database()
MISSION_STATE = {"quarantined": False, "restarted": False, "secured": False}

@mcp.tool()
async def get_active_alerts() -> str:
    """List all active security alerts."""
    return json.dumps(DB["soc"])

@mcp.tool()
async def resolve_ip_to_host(ip: str) -> str:
    """Resolve internal IP to hostname. Remedy: Validate IP range (10.0.4.x)."""
    if ip not in DB["noc"]: return f"Error: Validate IP range (10.0.4.x)."
    return json.dumps({"hostname": DB["noc"][ip]})

@mcp.tool()
async def query_node_logs(hostname: str, q: str = None) -> str:
    """Retrieve system logs. Remedy: Node logs require a verified Hostname (SRV-XXXX). Use q=EXFIL."""
    if hostname not in DB["it"]: return f"Error: Node logs require a verified Hostname (SRV-XXXX)."
    logs = DB["it"][hostname]
    if q: 
        search_term = q.replace("q=", "")
        logs = [l for l in logs if search_term.lower() in str(l).lower()]
    return json.dumps(logs)

@mcp.tool()
async def link_token_to_account(token: str) -> str:
    """Trace a transaction token. Remedy: Token RT-XXXX required."""
    if token not in DB["banking"]: return "Error: Token RT-XXXX required."
    return json.dumps({"account_id": DB["banking"][token]})

@mcp.tool()
async def audit_account_owner(account_id: str) -> str:
    """Identify employee ID. Remedy: Account IDs (ACC-XXXX) must be retrieved from the BANKING landmark."""
    if account_id not in DB["finance"]: return "Error: Account IDs (ACC-XXXX) must be retrieved from BANKING."
    return json.dumps({"employee_id": DB["finance"][account_id]})

@mcp.tool()
async def resolve_principal(employee_id: str) -> str:
    """Resolve Employee ID. Remedy: Employee IDs (EMP-XXXX) must be obtained from the FINANCE landmark."""
    if employee_id not in DB["hr"]: return "Error: Employee IDs (EMP-XXXX) must be obtained from FINANCE."
    return json.dumps({"username": DB["hr"][employee_id]})

@mcp.tool()
async def quarantine_principal(username: str, token: str) -> str:
    """Internal technical quarantine handler."""
    if username.startswith("EMP-"): return "Error: Mismatch! Use CORP-XX ID."
    emp_id = next((k for k, v in DB["hr"].items() if v == username), None)
    acc_id = next((k for k, v in DB["finance"].items() if v == emp_id), None)
    linked_token = next((k for k, v in DB["banking"].items() if v == acc_id), None)
    if not emp_id or linked_token != token: return "Error: Mismatch! Ensure username and token match."
    MISSION_STATE["quarantined"] = True
    return "SUCCESS"

@mcp.tool()
async def restart_node(hostname: str) -> str:
    """Reboot SRV-XXXX node."""
    if hostname != "SRV-FORENSIC-142": return "Error: Validate hostname (SRV-FORENSIC-142)."
    MISSION_STATE["restarted"] = True
    return "SUCCESS"

@mcp.tool()
async def secure_escrow() -> str:
    """Lock down risk capital in forensic escrow."""
    MISSION_STATE["secured"] = True
    return "SUCCESS"

@mcp.tool()
async def submit_gauntlet_report(incident_id: str, summary: str) -> str:
    """Submit final audit report."""
    if not all(MISSION_STATE.values()): 
        return "Error: MISSION INCOMPLETE. Ensure quarantine, restart, and secure are SUCCESS."
    if incident_id != "SEC-9982":
        return "Error: INVALID_INCIDENT_ID."
    return "MISSION_SUCCESS"

# --- NOISE TOOLS ---
for nl in ["legal", "marketing", "logistics", "facilities", "rnd", "procurement", "sales", "devops", "hiring", "strategy"]:
    for i in range(10):
        def make_noise(n=nl, idx=i):
            @mcp.tool(name=f"{n}_op_{idx}")
            async def noise_tool() -> str:
                return "restricted"
        make_noise()

if __name__ == "__main__":
    mcp.run()
