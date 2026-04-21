import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from elemm.fastapi import Elemm
from pydantic import BaseModel

class ReportReq(BaseModel):
    status: str
    detail: str

def test_mcp_export_comprehensive():
    app = FastAPI()
    ai = Elemm(agent_welcome="Test Mission", protocol_instructions="Test Rules")
    
    @app.post("/banking/freeze", tags=["banking"])
    @ai.landmark(id="freeze_account", type="action", description="Freeze account.")
    def freeze(account_id: str): return {"ok": True}
    
    @app.post("/report", tags=["root", "banking"])
    @ai.landmark(id="submit_report", type="action", description="Report.")
    def report(req: ReportReq): return {"ok": True}
    
    @app.get("/nav/banking")
    @ai.landmark(id="nav_banking", type="navigation", description="Nav.", opens_group="banking")
    def nav(): return {"ok": True}

    @app.get("/global")
    @ai.landmark(id="global_tool", type="action", description="Global.", global_access=True)
    def glob(): return {"ok": True}

    ai.bind_to_app(app)
    client = TestClient(app)
    
    # 1. Test Root Context
    resp = client.get("/.well-known/mcp-tools.json")
    tools = resp.json()
    ids = [t["name"] for t in tools]
    assert "nav_banking" not in ids # Now separated into 'navigation' list
    assert "global_tool" in ids
    assert "freeze_account" not in ids # Isolated in banking group
    
    # Check Context Prefix on any root tool
    report_tool = next(t for t in tools if t["name"] == "submit_report")
    assert "[Module: root] TOOL: Report." in report_tool["description"]
    
    # 2. Test Banking Context
    resp = client.get("/.well-known/mcp-tools.json?group=banking")
    tools = resp.json()
    ids = [t["name"] for t in tools]
    assert "freeze_account" in ids
    assert "submit_report" in ids
    assert "global_tool" in ids # Global access
    
    # 3. Test Parameter Mapping (Pydantic)
    report_tool = next(t for t in tools if t["name"] == "submit_report")
    props = report_tool["inputSchema"]["properties"]
    assert "status" in props
    assert "detail" in props
    assert "req" not in props # Filtered out
