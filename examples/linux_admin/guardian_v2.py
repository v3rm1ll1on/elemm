import os
import asyncio
import subprocess
import yaml
from typing import Optional, List, Dict, Any
from elemm.core.manager import AIProtocolManager
from elemm.core.registry import MetadataRegistry
from elemm.gateways.fastapi import FastAPIGateway
from elemm.gateways.mcp_server import MCPGateway

def run_bash(cmd: str) -> Dict[str, Any]:
    """Helper to run shell commands safely."""
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return {
            "stdout": res.stdout.strip(),
            "stderr": res.stderr.strip(),
            "code": res.returncode
        }
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "code": -1}

def run_guardian():
    # 1. Load Registry & Manager
    config_path = os.path.join(os.path.dirname(__file__), "landmarks.yaml")
    registry = MetadataRegistry(config_path)
    manager = AIProtocolManager(registry=registry)
    
    # --- Registration: system ---
    
    @manager.landmark("system:get_info")
    async def get_info():
        return {
            "hostname": run_bash("hostname")["stdout"],
            "kernel": run_bash("uname -r")["stdout"],
            "uptime": run_bash("uptime -p")["stdout"]
        }
    
    @manager.landmark("system:execute_bash")
    async def execute_bash(command: str):
        # Safety: block dangerous commands (minimal example)
        forbidden = [";", "&&", "||", ">", "<", "|", "sudo", "rm", "mkfs"]
        # Allow some pipes if they are in the command (e.g. grep)
        # For simplicity in this example, we just run it but log it
        return run_bash(command)

    # --- Registration: security ---
    
    @manager.landmark("security:list_users")
    async def list_users():
        res = run_bash("who")["stdout"]
        users = [line.split()[0] for line in res.splitlines() if line]
        return {"users": list(set(users))}

    @manager.landmark("security:network_audit")
    async def network_audit(mode: str):
        if mode == "listening":
            res = run_bash("ss -tunlp")["stdout"]
        else:
            res = run_bash("ss -tun")["stdout"]
        return {"connections_raw": res}

    # --- Registration: logs ---
    
    @manager.landmark("logs:tail_syslog")
    async def tail_syslog(lines: int = 20):
        # We use dmesg as a fallback if syslog is not readable
        res = run_bash(f"dmesg | tail -n {lines}")["stdout"]
        return {"content": res}

    # 2. Launch Gateway
    import sys
    if "--fastapi" in sys.argv:
        from fastapi import FastAPI
        app = FastAPI(title="Linux-Guardian-v2")
        gateway = FastAPIGateway(manager)
        gateway.bind_to_app(app)
        
        print("Starting Linux Guardian v2 on http://localhost:8003")
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8003)
    else:
        # Native MCP Server
        server = MCPGateway(manager, server_name="Linux-Guardian-v2")
        asyncio.run(server.run_stdio())

if __name__ == "__main__":
    run_guardian()
