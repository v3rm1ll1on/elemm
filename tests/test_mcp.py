import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from elemm import Elemm
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
    
    from elemm.mcp.bridge import LandmarkBridge
    bridge = LandmarkBridge(manager=ai)
    tools = bridge.get_full_mcp_definitions()
    
    ids = [t["name"] for t in tools]
    # In get_full_mcp_definitions, all tools are returned
    assert "global_tool" in ids
    assert "freeze_account" in ids
    
    # 3. Test Parameter Mapping (Pydantic)
    report_tool = next(t for t in tools if t["name"] == "submit_report")
    props = report_tool["inputSchema"]["properties"]
    assert "status" in props
    assert "detail" in props
    assert "req" not in props # Filtered out
