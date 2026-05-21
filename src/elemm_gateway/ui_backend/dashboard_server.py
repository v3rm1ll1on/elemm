# Copyright (C) 2026 Marc Stöcker
# Part of Elemm v1.2.0 - Dashboard Backend Module

import os
import json
import time
import asyncio
import logging
import sys
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any
import yaml

# Ensure project root is in path for absolute imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

# Internal Elemm Imports
from elemm_gateway.services.manifest_service import ManifestService
from elemm_gateway.components import VaultManager
from elemm_gateway import __version__
from elemm.core.schema import SignatureGenerator

logger = logging.getLogger(__name__)

app = FastAPI(title="Elemm Gateway Dashboard API")

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

# Paths
CONFIG_DIR = os.path.expanduser("~/.elemm")
VAULT_PATH = os.path.join(CONFIG_DIR, "vault.json")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

# In-Memory Master State
GLOBAL_STATE = {
    "active_sites_count": 0,
    "total_tokens": 0,
    "landmark_count": 0,
    "last_action": "Waiting for data...",
    "tokens_in": 0,
    "tokens_out": 0,
    "chars_in": 0,
    "chars_out": 0,
    "version": __version__,
    "status": "online",
    "sessions": {}, # Session-specific stats
    "manifests": {} # session_id -> manifest string
}

# Boot time for Uptime calc
START_TIME = time.time()

vault_manager = VaultManager(VAULT_PATH)

def get_current_security_policy():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                config = json.load(f)
            ui_config = config.get("ui", {})
            if ui_config.get("simulate_security_policy", False):
                from elemm_gateway.services.security import SecurityPolicy
                return SecurityPolicy(config)
        except Exception as e:
            logger.error(f"Failed to load SecurityPolicy in backend: {e}")
    return None

@app.get("/api/v1/inspect")
async def inspect_site(url: str, landmark_id: str = None, session_id: str = "default"):
    """
    Lazy-loads a manifest for a given URL by importing the gateway logic.
    """
    try:
        # Reload vault before inspection to get latest keys
        vault_manager.vault = vault_manager.load()
        
        result = await ManifestService.inspect_url(url, landmark_id=landmark_id, vault_manager=vault_manager, output_format="json")
        if result["status"] == "success":
            # Apply server-side client emulation of active Guardian Security Policy
            policy = get_current_security_policy()
            if policy:
                # 1. Filter result["tools"]
                if "tools" in result and isinstance(result["tools"], list):
                    result["tools"] = [
                        t for t in result["tools"]
                        if policy.is_action_allowed(
                            t.get("name") or t.get("id") if isinstance(t, dict) else (t.name if hasattr(t, "name") else t.id),
                            method=t.get("method") or t.get("meta", {}).get("method") if isinstance(t, dict) else (t.method if hasattr(t, "method") else (t.meta.get("method") if hasattr(t, "meta") else None))
                        )["allowed"]
                    ]
                # 2. Filter result["landmarks"]
                if "landmarks" in result:
                    if isinstance(result["landmarks"], dict):
                        result["landmarks"] = {
                            id: data for id, data in result["landmarks"].items()
                            if policy.is_action_allowed(
                                id,
                                method=data.get("method") or data.get("meta", {}).get("method") if isinstance(data, dict) else (data.method if hasattr(data, "method") else None)
                            )["allowed"]
                        }
                    elif isinstance(result["landmarks"], list):
                        result["landmarks"] = [
                            lm for lm in result["landmarks"]
                            if policy.is_action_allowed(
                                lm.get("id") or lm.get("name") if isinstance(lm, dict) else (lm.id if hasattr(lm, "id") else lm.name),
                                method=lm.get("method") or lm.get("meta", {}).get("method") if isinstance(lm, dict) else (lm.method if hasattr(lm, "method") else None)
                            )["allowed"]
                        ]
                # 3. Filter result["data"]["landmarks"]
                if "data" in result and isinstance(result["data"], dict) and "landmarks" in result["data"]:
                    if isinstance(result["data"]["landmarks"], dict):
                        result["data"]["landmarks"] = {
                            id: data for id, data in result["data"]["landmarks"].items()
                            if policy.is_action_allowed(
                                id,
                                method=data.get("method") or data.get("meta", {}).get("method") if isinstance(data, dict) else (data.method if hasattr(data, "method") else None)
                            )["allowed"]
                        }
                    elif isinstance(result["data"]["landmarks"], list):
                        result["data"]["landmarks"] = [
                            lm for lm in result["data"]["landmarks"]
                            if policy.is_action_allowed(
                                lm.get("id") or lm.get("name") if isinstance(lm, dict) else (lm.id if hasattr(lm, "id") else lm.name),
                                method=lm.get("method") or lm.get("meta", {}).get("method") if isinstance(lm, dict) else (lm.method if hasattr(lm, "method") else None)
                            )["allowed"]
                        ]
            # 1. Store Manifest String (Ensure it's a string for the UI parser)
            manifest_content = result.get("manifest")
            if not manifest_content and "data" in result:
                # If no manifest string provided, use the bridge's virtual manifest
                manifest_content = result["data"].get("manifest") or json.dumps(result["data"])
                result["manifest"] = manifest_content
            
            GLOBAL_STATE["manifests"][session_id] = manifest_content
            
            # 2. Ensure session entry exists
            if session_id not in GLOBAL_STATE["sessions"]:
                GLOBAL_STATE["sessions"][session_id] = {
                    "tokens_in": 0, "tokens_out": 0, "total_tokens": 0,
                    "chars_in": 0, "chars_out": 0, "total_chars": 0,
                    "landmark_count": 0, "version": __version__,
                    "last_action": "Manual Inspection",
                    "last_seen": time.time(),
                    "history": [],
                    "tools": [] # Cached tool definitions for execution
                }
            
            # 3. Store Metadata and Tools
            session = GLOBAL_STATE["sessions"][session_id]
            session["active_url"] = url
            session["site_type"] = result.get("type", "native")
            
            if "tools" in result:
                session["tools"] = result["tools"]
            elif "landmarks" in result:
                session["tools"] = result["landmarks"]
            elif "data" in result:
                # Store parsed tools from native if available
                session["tools"] = result["data"].get("landmarks", [])
            
            return result
        else:
            raise HTTPException(status_code=400, detail=result["message"])
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Inspect failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/inspect/landmark")
async def inspect_landmark(landmark_id: str, url: str = None, session_id: str = "default"):
    """
    Fetches the technical signature for a specific landmark, prioritizing session cache.
    """
    try:
        policy = get_current_security_policy()
        if policy:
            if not policy.is_action_allowed(landmark_id)["allowed"]:
                raise HTTPException(status_code=403, detail=f"Access to action/landmark '{landmark_id}' is restricted by Security Policy.")

        session = GLOBAL_STATE["sessions"].get(session_id)
        if not url and session:
            url = session.get("active_url")
        
        site_type = session.get("site_type", "native") if session else "native"

        # 1. Try to find in session cache first (Standardized Elemm Format)
        if session and session.get("tools"):
            # The tools in session are already normalized by ManifestService.normalize_bridge_to_elemm
            tool = next((t for t in session["tools"] if t.get("id") == landmark_id or t.get("name") == landmark_id), None)
            if tool:
                # If it's a raw bridge tool, we need to map inputSchema to parameters
                if "inputSchema" in tool and "parameters" not in tool:
                    params = []
                    schema = tool.get("inputSchema", {})
                    req_fields = schema.get("required", [])
                    for p_name, p_def in schema.get("properties", {}).items():
                        params.append({
                            "name": p_name,
                            "type": p_def.get("type", "string"),
                            "description": p_def.get("description", ""),
                            "required": p_name in req_fields,
                            "location": p_def.get("location", "body")
                        })
                    frontend_tool = {
                        "id": tool.get("name", ""),
                        "name": tool.get("name", ""),
                        "is_tool": True,
                        "description": tool.get("description", ""),
                        "parameters": params,
                        "returns": tool.get("returns", "any"),
                        "outputSchema": tool.get("outputSchema", {}),
                        "remedy": tool.get("remedy", ""),
                        "meta": tool.get("meta", {})
                    }
                else:
                    frontend_tool = tool

                # Generate or sync signature
                res = {"status": "success", "type": site_type, "data": frontend_tool}
                if site_type == "native":
                    try:
                        res["signature"] = SignatureGenerator.to_typescript_signature(frontend_tool)
                    except Exception as e:
                        logger.warning(f"Failed to generate signature for native tool {landmark_id}: {e}")
                elif site_type != "native" and not frontend_tool.get("signature"):
                    res["signature"] = f"// {site_type.upper()} Tool: {landmark_id}\n// Parameters mapped to Elemm JSON."
                return res

        # 2. Fallback to ManifestService (For Native or if cache is cold)
        if not url:
            raise HTTPException(status_code=400, detail="No active URL found for this session.")

        result = await ManifestService.inspect_landmark(
            url, landmark_id, vault_manager=vault_manager, output_format="json", site_type=site_type
        )
        if isinstance(result, dict) and result.get("status") == "success":
            data = result.get("data")
            if data and site_type == "native" and not result.get("signature"):
                try:
                    result["signature"] = SignatureGenerator.to_typescript_signature(data)
                except Exception as e:
                    logger.warning(f"Failed to generate fallback signature for native tool {landmark_id}: {e}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Landmark inspect failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/search")
async def search_landmarks(query: str, url: str = None, session_id: str = "default", limit: int = 50, offset: int = 0):
    """
    Searches for landmarks across the protocol, utilizing hybrid (remote/local) search.
    """
    try:
        session = GLOBAL_STATE["sessions"].get(session_id)
        if not url and session:
            url = session.get("active_url")
        
        if not url:
            raise HTTPException(status_code=400, detail="No active URL found for search.")
            
        # We pass the full session data to allow local bridging search if needed
        site_data = {
            "type": session.get("site_type", "native") if session else "native",
            "tools": session.get("tools", []) if session else []
        }
        
        result = await ManifestService.search_landmarks(
            url, site_data, query, limit=limit, offset=offset, output_format="json"
        )
        
        policy = get_current_security_policy()
        if policy and "landmarks" in result:
            if isinstance(result["landmarks"], list):
                result["landmarks"] = [
                    lm for lm in result["landmarks"]
                    if policy.is_action_allowed(
                        lm.get("id") or lm.get("name") if isinstance(lm, dict) else (lm.id if hasattr(lm, "id") else lm.name),
                        method=lm.get("method") or lm.get("meta", {}).get("method") if isinstance(lm, dict) else (lm.method if hasattr(lm, "method") else None)
                    )["allowed"]
                ]
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/execute")
async def execute_action(payload: dict):
    """
    Executes a specific action on the remote site using cached session data.
    """
    url = payload.get("url")
    action = payload.get("action")
    parameters = payload.get("parameters", {})
    session_id = payload.get("session_id", "default")
    
    if not url or not action:
        raise HTTPException(status_code=400, detail="Missing URL or action")
        
    try:
        from elemm_gateway.components import OpenAPIExecutor, GraphQLExecutor
        import httpx
        
        session = GLOBAL_STATE["sessions"].get(session_id, {})
        site_type = session.get("site_type", "native")
        logger.info(f"Execution request: {action} on {url} (Type: {site_type})")
        
        # 1. Bridge Execution (OpenAPI/GraphQL)
        if site_type in ["openapi", "graphql"]:
            cached_tools = session.get("tools", [])
            # Use .get("name") and fallback to .get("id") to be robust
            tool_data = next((t for t in cached_tools if isinstance(t, dict) and (t.get("name") == action or t.get("id") == action)), None)
            
            if not tool_data:
                logger.warning(f"Tool {action} not found in cache. Available: {[t.get('name', t.get('id')) for t in cached_tools]}")
                raise HTTPException(status_code=404, detail=f"Tool '{action}' not found in session cache. Try 'inspect_landmark' first.")
            
            if site_type == "openapi":
                executor = OpenAPIExecutor(vault_manager)
            else:
                executor = GraphQLExecutor(vault_manager)
                
            result_str = await executor.execute(tool_data, parameters)
            try:
                return json.loads(result_str)
            except:
                return {"result": result_str}
        
        # 2. Native Elemm Route
        async with httpx.AsyncClient() as client:
            base_url = url.split("/.well-known")[0].rstrip("/")
            exec_url = f"{base_url}/.well-known/elemm/execute"
            
            resp = await client.post(exec_url, json={"action": action, "parameters": parameters}, timeout=30.0)
            if resp.status_code != 200:
                logger.error(f"Native execution failed: {resp.status_code} - {resp.text}")
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
                
            return resp.json()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Execution failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_uptime():
    seconds = int(time.time() - START_TIME)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if days > 0:
        return f"{days}d {hours}h"
    return f"{hours}h {minutes}m {seconds}s"

@app.get("/api/v1/status")
async def get_status():
    """Returns the aggregated in-memory gateway status."""
    config = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                config = json.load(f)
        except:
            pass

    sec_config = config.get("security", {})
    disallowed = sec_config.get("disallowed_patterns", [])
    level = "hardened" if len(disallowed) > 0 else "standard"
    
    # Count active clients (seen in last 5 mins) and cleanup old ones (> 24h)
    now = time.time()
    expired_sessions = [sid for sid, s in GLOBAL_STATE["sessions"].items() if now - s.get("last_seen", 0) > 86400]
    for sid in expired_sessions:
        del GLOBAL_STATE["sessions"][sid]

    active_clients = len([s for s in GLOBAL_STATE["sessions"].values() if now - s.get("last_seen", 0) < 300])
    
    # Count unique active URLs across all active sessions
    active_urls = {s.get("active_url") for s in GLOBAL_STATE["sessions"].values() if now - s.get("last_seen", 0) < 300 and s.get("active_url")}
    active_sites = len(active_urls)
    GLOBAL_STATE["active_sites_count"] = active_sites
    
    return {
        **GLOBAL_STATE,
        "uptime": get_uptime(),
        "security_level": level,
        "active_clients": active_clients,
        "active_sites": active_sites
    }

@app.post("/api/v1/reset")
async def reset_dashboard():
    """Clears history and resets statistics, preserving active sessions."""
    GLOBAL_STATE["last_action"] = "History Cleared"
    GLOBAL_STATE["tokens_in"] = 0
    GLOBAL_STATE["tokens_out"] = 0
    GLOBAL_STATE["chars_in"] = 0
    GLOBAL_STATE["chars_out"] = 0
    GLOBAL_STATE["total_tokens"] = 0
    GLOBAL_STATE["total_chars"] = 0
    GLOBAL_STATE["active_sites_count"] = 0
    GLOBAL_STATE["landmark_count"] = 0
    
    # Clear all global history
    GLOBAL_STATE["history"] = []
    
    # Reset history and counters inside each session but keep them registered
    for sid, session in GLOBAL_STATE["sessions"].items():
        session["history"] = []
        session["last_action"] = "History Cleared"
        session["tokens_in"] = 0
        session["tokens_out"] = 0
        session["chars_in"] = 0
        session["chars_out"] = 0
        session["total_tokens"] = 0
        session["total_chars"] = 0
    
    return {"status": "success", "message": "History and statistics cleared. Active sessions preserved."}

@app.get("/api/v1/system/env")
async def get_system_env():
    import getpass
    import platform
    import shutil
    import sys

    os_type = "linux"
    wsl_distro = ""
    if platform.system().lower() == "windows":
        os_type = "windows"
    elif "microsoft" in platform.release().lower() or "wsl" in platform.release().lower():
        os_type = "wsl"
        wsl_distro = os.environ.get("WSL_DISTRO_NAME", "Ubuntu")
    elif platform.system().lower() == "darwin":
        os_type = "mac"

    user = getpass.getuser()
    
    # Try to find the wrapper script directly
    executable_path = shutil.which("elemm-gateway")
    if not executable_path:
        # Fallback to absolute python path
        executable_path = f"{sys.executable} -m elemm_gateway.cli"

    return {
        "os": os_type,
        "wsl_distro": wsl_distro,
        "user": user,
        "executable_path": executable_path,
        "host_ip": "localhost",
        "port": 8000
    }

CONFIG_PATH = os.path.expanduser("~/.elemm/config.json")

@app.get("/api/v1/config")
async def get_config():
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
        return {
            "security": {"disallowed_patterns": [], "disallowed_landmarks": [], "allowed_methods": []},
            "limit_standard": 30000, "limit_inspect": 20000, "timeout_seconds": 30,
            "retry_attempts": 3, "retry_delay_ms": 1000,
            "ui": {"display_mode": "tokens", "char_to_token_ratio": 4.0}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/config")
async def update_config(config: dict):
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)
        return {"status": "success", "message": "Configuration updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/vault")
async def get_vault():
    try:
        if os.path.exists(VAULT_PATH):
            with open(VAULT_PATH, "r") as f:
                return json.load(f)
        return {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/vault")
async def update_vault(vault: dict):
    # 1. Load existing vault to check for deletions
    existing_keys = set()
    if os.path.exists(VAULT_PATH):
        try:
            with open(VAULT_PATH, "r") as f:
                existing_keys = set(json.load(f).keys())
        except Exception as e:
            logger.error(f"Failed to load existing vault for delete check: {e}")

    # Determine deleted keys
    new_keys = set(vault.keys())
    deleted_keys = existing_keys - new_keys

    # 2. Check if any deleted key is in use in MCP Server Config
    if deleted_keys:
        mcp_servers = {}
        if os.path.exists(MCP_CONFIG_PATH):
            try:
                with open(MCP_CONFIG_PATH, "r", encoding="utf-8") as f:
                    mcp_data = yaml.safe_load(f) or {}
                    mcp_servers = mcp_data.get("servers", {}) or {}
            except Exception as e:
                logger.error(f"Failed to load MCP configuration for vault delete validation: {e}")

        conflicts = {}
        for key in deleted_keys:
            using_servers = []
            target = f"vault:{key}"
            
            def check_value(val: Any) -> bool:
                if isinstance(val, str):
                    return val == target or val.startswith(target + ":") or val.startswith(target)
                if isinstance(val, list):
                    return any(check_value(item) for item in val)
                if isinstance(val, dict):
                    return any(check_value(v) for v in val.values())
                return False
            
            for srv_id, srv_conf in mcp_servers.items():
                if srv_conf and check_value(srv_conf):
                    using_servers.append(srv_id)
            
            if using_servers:
                conflicts[key] = using_servers

        if conflicts:
            conflict_details = []
            for key, servers in conflicts.items():
                servers_str = ", ".join(servers)
                conflict_details.append(f"Key '{key}' is actively used by the following MCP servers: {servers_str}")
            detail_msg = "; ".join(conflict_details)
            raise HTTPException(
                status_code=400,
                detail=f"Deletion blocked: {detail_msg}. Please remove vault references from your MCP configuration first."
            )

    try:
        os.makedirs(os.path.dirname(VAULT_PATH), exist_ok=True)
        with open(VAULT_PATH, "w") as f:
            json.dump(vault, f, indent=2)
        return {"status": "success", "message": "Vault updated successfully"}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/vault/check-delete/{key}")
async def check_vault_delete(key: str):
    try:
        # Load MCP config
        mcp_servers = {}
        if os.path.exists(MCP_CONFIG_PATH):
            with open(MCP_CONFIG_PATH, "r", encoding="utf-8") as f:
                try:
                    mcp_data = yaml.safe_load(f) or {}
                    mcp_servers = mcp_data.get("servers", {}) or {}
                except Exception as e:
                    logger.error(f"Failed to parse MCP config during check-delete: {e}")

        # Check if the key is used in MCP config
        using_servers = []
        target = f"vault:{key}"
        
        def check_value(val: Any) -> bool:
            if isinstance(val, str):
                return val == target or val.startswith(target + ":") or val.startswith(target)
            if isinstance(val, list):
                return any(check_value(item) for item in val)
            if isinstance(val, dict):
                return any(check_value(v) for v in val.values())
            return False
        
        for srv_id, srv_conf in mcp_servers.items():
            if srv_conf and check_value(srv_conf):
                using_servers.append(srv_id)

        if using_servers:
            servers_str = ", ".join(using_servers)
            raise HTTPException(
                status_code=400,
                detail=f"Deletion blocked: Key '{key}' is actively used by the following MCP servers: {servers_str}. Please remove vault references from your MCP configuration first."
            )

        return {"status": "success", "message": "Credential is safe to delete"}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


MCP_CONFIG_PATH = os.path.expanduser("~/.elemm/mcp_servers.yaml")

@app.get("/api/v1/mcp/config")
async def get_mcp_config():
    try:
        if os.path.exists(MCP_CONFIG_PATH):
            with open(MCP_CONFIG_PATH, "r", encoding="utf-8") as f:
                yaml_content = f.read()
        else:
            yaml_content = (
                "version: \"1.0\"\n"
                "servers:\n"
                "  # Beispiel-Server:\n"
                "  # github:\n"
                "  #   name: \"GitHub MCP Server\"\n"
                "  #   transport: \"stdio\"\n"
                "  #   command: \"npx\"\n"
                "  #   args: [\"-y\", \"@modelcontextprotocol/server-github\"]\n"
                "  #   env:\n"
                "  #     GITHUB_PERSONAL_ACCESS_TOKEN: \"env:GITHUB_TOKEN\"\n"
            )
            os.makedirs(os.path.dirname(MCP_CONFIG_PATH), exist_ok=True)
            with open(MCP_CONFIG_PATH, "w", encoding="utf-8") as f:
                f.write(yaml_content)
                
        try:
            parsed = yaml.safe_load(yaml_content)
            if not isinstance(parsed, dict):
                parsed = {}
        except:
            parsed = {}
            
        parsed_servers = parsed.get("servers", {})
        if parsed_servers is None:
            parsed_servers = {}
            
        return {
            "yaml": yaml_content,
            "servers": parsed_servers
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/mcp/config")
async def update_mcp_config(payload: dict):
    yaml_content = payload.get("yaml")
    if not yaml_content:
        raise HTTPException(status_code=400, detail="Missing 'yaml' content in payload")
        
    try:
        parsed = yaml.safe_load(yaml_content)
        if not isinstance(parsed, dict) or "version" not in parsed:
            raise ValueError("Configuration must be a dictionary and contain a 'version' field.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML configuration: {str(e)}")
        
    try:
        with open(MCP_CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(yaml_content)
        return {"status": "success", "message": "MCP Configuration updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/mcp/server/{server_id}")
async def delete_mcp_server(server_id: str):
    try:
        # Load existing config
        if os.path.exists(MCP_CONFIG_PATH):
            with open(MCP_CONFIG_PATH, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        else:
            config = {"version": "1.0", "servers": {}}

        # Ensure servers dictionary exists
        if "servers" not in config:
            config["servers"] = {}

        # Check if server exists
        if server_id not in config["servers"]:
            raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found.")

        # Remove server
        del config["servers"][server_id]

        # Write config back
        with open(MCP_CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f, sort_keys=False)

        return {"status": "success", "message": f"Server '{server_id}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/mcp/import")
async def import_mcp_config(payload: dict):
    text = payload.get("text", "")
    migrate_to_vault = payload.get("migrate_to_vault", True)
    if not text.strip():
        raise HTTPException(status_code=400, detail="Import text cannot be empty.")
        
    import json
    import yaml
    
    # 1. Parse JSON or YAML
    parsed_config = None
    try:
        parsed_config = json.loads(text)
    except Exception:
        try:
            parsed_config = yaml.safe_load(text)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse as JSON or YAML: {str(e)}")
            
    if not isinstance(parsed_config, dict):
        raise HTTPException(status_code=400, detail="Configuration must be an object/dictionary.")
        
    # 2. Extract server dictionary
    imported_servers = {}
    if "mcpServers" in parsed_config:
        imported_servers = parsed_config["mcpServers"]
    elif "servers" in parsed_config:
        imported_servers = parsed_config["servers"]
    else:
        imported_servers = parsed_config
        
    if not isinstance(imported_servers, dict):
        raise HTTPException(status_code=400, detail="No server definitions found in imported configuration.")
        
    # 3. Load active config
    from elemm_gateway.services.mcp_config import MCPConfigManager
    manager = MCPConfigManager(MCP_CONFIG_PATH)
    active_servers = manager.get_servers()
    
    # Load current vault
    vault = vault_manager.vault
    vault_updated = False
    
    imported_count = 0
    for server_id, server_conf in imported_servers.items():
        if not isinstance(server_conf, dict):
            continue
            
        name = server_conf.get("name") or server_id.capitalize()
        url = server_conf.get("url")
        command = server_conf.get("command")
        
        # Determine transport: if 'url' is present, default to "sse", else "stdio"
        default_transport = "sse" if url else "stdio"
        transport = server_conf.get("transport") or default_transport
        
        if not command and not url:
            continue
            
        args = server_conf.get("args") or []
        env = server_conf.get("env") or {}
        instructions = server_conf.get("instructions") or ""
        remedies = server_conf.get("remedies") or {}

        # Avoid overwriting existing MCP server definitions by renaming!
        base_server_id = server_id
        server_id_counter = 1
        while server_id in active_servers:
            existing = active_servers[server_id]
            if (existing.get("command") == command and 
                existing.get("url") == url and
                existing.get("args") == args and 
                existing.get("env") == env and
                existing.get("transport") == transport):
                # Perfectly identical server already exists, we can reuse/overwrite without renaming
                break
            
            # Different configuration, rename server_id to avoid conflict!
            server_id = f"{base_server_id}_{server_id_counter}"
            server_id_counter += 1
            name = f"{server_conf.get('name') or base_server_id.capitalize()} ({server_id_counter - 1})"
            
        # Migrate env variables to Vault if requested
        if migrate_to_vault and isinstance(env, dict):
            migrated_env = {}
            for k, v in env.items():
                if isinstance(v, str) and v.strip() and not v.startswith("env:") and not v.startswith("vault:"):
                    sensitive_words = ["token", "key", "secret", "password", "pat", "auth", "pwd"]
                    is_sensitive = any(word in k.lower() for word in sensitive_words) or len(v) > 15
                    if is_sensitive:
                        base_key = f"IMPORTED_{server_id.upper()}_{k.upper()}"
                        vault_key = base_key
                        vault_key_counter = 1
                        while vault_key in vault:
                            # If the existing key has the exact same value/type, reuse it!
                            if vault[vault_key].get("value") == v and vault[vault_key].get("type") == "envVar":
                                break
                            # Different value, rename key to avoid conflict!
                            vault_key = f"{base_key}_{vault_key_counter}"
                            vault_key_counter += 1
                        
                        vault[vault_key] = {
                            "type": "envVar",
                            "value": v
                        }
                        migrated_env[k] = f"vault:{vault_key}"
                        vault_updated = True
                        continue
                migrated_env[k] = v
            env = migrated_env
            
        active_servers[server_id] = {
            "name": name,
            "transport": transport,
            "command": command,
            "url": url,
            "args": args,
            "env": env,
            "instructions": instructions,
            "remedies": remedies
        }
        imported_count += 1
        
    if imported_count == 0:
        raise HTTPException(status_code=400, detail="No valid MCP servers with a 'command' or 'url' could be imported.")
        
    # Save vault if updated
    if vault_updated:
        vault_manager.vault = vault
        try:
            with open(VAULT_PATH, "w") as f:
                json.dump(vault, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save vault during import: {e}")
            
    # Save configuration
    new_config = {
        "version": manager.config.get("version", "1.0"),
        "servers": active_servers
    }
    
    try:
        with open(MCP_CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.safe_dump(new_config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write updated YAML config: {e}")
        
    return {
        "status": "success",
        "message": f"Successfully imported {imported_count} server(s) to configuration.",
        "vault_migrated": vault_updated
    }

@app.get("/api/v1/mcp/test/{server_id}")
async def test_mcp_server(server_id: str):
    import subprocess
    import json
    import select
    from elemm_gateway.services.mcp_config import MCPConfigManager
    
    manager = MCPConfigManager(MCP_CONFIG_PATH)
    server_conf = manager.get_server(server_id)
    if not server_conf:
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found in configuration.")
        
    transport = server_conf.get("transport", "stdio")
    url = server_conf.get("url")
    command = server_conf.get("command")
    
    if transport == "sse" or url:
        if not url:
            raise HTTPException(status_code=400, detail="SSE transport requires a 'url' configuration.")
            
        # Resolve env vars (only what is explicitly configured for this server in its 'env' section!)
        resolved_env = manager.get_resolved_env(server_id, vault_manager=vault_manager)
        headers = {}
        for k, v in resolved_env.items():
            k_upper = k.upper()
            if k_upper == "AUTHORIZATION":
                headers["Authorization"] = v
            elif k_upper in ("API_KEY", "API-KEY"):
                headers["X-API-Key"] = v
            elif k_upper in ("TOKEN", "BEARER_TOKEN") or k_upper in ("NOTION", "NOTION_TOKEN") or v.startswith("ntn_"):
                headers["Authorization"] = v if v.startswith("Bearer ") else f"Bearer {v}"
            else:
                headers[k] = v
                
        import httpx
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(url, headers=headers)
                if response.status_code == 401:
                    try:
                        resp_body = response.text
                    except Exception:
                        resp_body = ""
                    return {
                        "status": "warning",
                        "message": f"Server reached, but authentication is required (HTTP 401 Unauthorized).\nResponse from server: {resp_body}",
                        "tools": []
                    }
                elif response.status_code == 403:
                    try:
                        resp_body = response.text
                    except Exception:
                        resp_body = ""
                    return {
                        "status": "warning",
                        "message": f"Server reached, but access was forbidden (HTTP 403 Forbidden).\nResponse from server: {resp_body}",
                        "tools": []
                    }
                elif response.status_code >= 400:
                    return {
                        "status": "error",
                        "message": f"Remote SSE server returned error code {response.status_code} at {url} (HTTP {response.status_code}).",
                        "tools": []
                    }
                return {
                    "status": "success",
                    "message": f"Successfully reached remote SSE server at {url} (HTTP {response.status_code}).",
                    "tools": []
                }
        except httpx.RequestError as exc:
            return {
                "status": "error",
                "message": f"Failed to connect to remote SSE server at {url}: {exc}",
                "tools": []
            }
            
    if not command:
        raise HTTPException(status_code=400, detail="Server has no command configured.")
        
    args = server_conf.get("args", [])
    env = os.environ.copy()
    resolved_env = manager.get_resolved_env(server_id, vault_manager=vault_manager)
    env.update(resolved_env)
    
    if transport != "stdio":
        return {
            "status": "success",
            "message": f"Transport '{transport}' configured. Connection testing only simulated for non-stdio.",
            "tools": []
        }
        
    proc = None
    try:
        proc = subprocess.Popen(
            [command] + args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
            bufsize=1
        )
        
        # 1. Send initialize
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "elemm-gateway-tester", "version": "1.0"}
            }
        }
        proc.stdin.write(json.dumps(init_req) + "\n")
        proc.stdin.flush()
        
        # Wait up to 3 seconds for response
        r, _, _ = select.select([proc.stdout], [], [], 3.0)
        if not r:
            proc.kill()
            _, stderr = proc.communicate(timeout=1.0)
            raise Exception(f"Timeout waiting for 'initialize' response from MCP server. Stderr: {stderr}")
            
        init_resp_line = proc.stdout.readline()
        if not init_resp_line:
            raise Exception("Process closed stdout unexpectedly during handshake.")
            
        init_resp = json.loads(init_resp_line)
        if "error" in init_resp:
            raise Exception(f"Initialize error: {init_resp['error']}")
            
        # 2. Send initialized notification
        init_notif = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        proc.stdin.write(json.dumps(init_notif) + "\n")
        proc.stdin.flush()
        
        # 3. Send tools/list
        list_req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        proc.stdin.write(json.dumps(list_req) + "\n")
        proc.stdin.flush()
        
        r, _, _ = select.select([proc.stdout], [], [], 3.0)
        if not r:
            proc.kill()
            raise Exception("Timeout waiting for 'tools/list' response from MCP server.")
            
        list_resp_line = proc.stdout.readline()
        if not list_resp_line:
            raise Exception("Process closed stdout unexpectedly during tools/list query.")
            
        list_resp = json.loads(list_resp_line)
        if "error" in list_resp:
            raise Exception(f"Tools list query returned error: {list_resp['error']}")
            
        tools = list_resp.get("result", {}).get("tools", [])
        
        # Cleanup
        proc.terminate()
        try:
            proc.wait(timeout=1.0)
        except:
            proc.kill()
            
        return {
            "status": "success",
            "message": "Connection and JSON-RPC handshake successful!",
            "tools": tools
        }
    except Exception as e:
        if proc:
            try:
                proc.kill()
            except:
                pass
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/mcp/execute/{server_id}/{tool_name}")
async def execute_mcp_tool(server_id: str, tool_name: str, payload: dict):
    import subprocess
    import json
    import select
    from elemm_gateway.services.mcp_config import MCPConfigManager
    
    manager = MCPConfigManager(MCP_CONFIG_PATH)
    server_conf = manager.get_server(server_id)
    if not server_conf:
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found in configuration.")
        
    command = server_conf.get("command")
    if not command:
        raise HTTPException(status_code=400, detail="Server has no command configured.")
        
    args = server_conf.get("args", [])
    
    # 0. Check Security Guard Policy
    policy = get_current_security_policy()
    if policy:
        allowed_res = policy.is_action_allowed(tool_name, method="mcp")
        if not allowed_res["allowed"]:
            raise HTTPException(
                status_code=403,
                detail=f"Security Guard: Execution of tool '{tool_name}' blocked. Reason: {allowed_res.get('reason', 'Access Denied')}"
            )
            
    env = os.environ.copy()
    resolved_env = manager.get_resolved_env(server_id, vault_manager=vault_manager)
    env.update(resolved_env)
    
    arguments = payload.get("arguments", {})
    
    transport = server_conf.get("transport", "stdio")
    if transport != "stdio":
        raise HTTPException(status_code=400, detail=f"Execution not supported for non-stdio transport '{transport}'.")
        
    proc = None
    try:
        proc = subprocess.Popen(
            [command] + args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
            bufsize=1
        )
        
        # 1. Initialize Handshake
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "elemm-gateway-tester", "version": "1.0"}
            }
        }
        proc.stdin.write(json.dumps(init_req) + "\n")
        proc.stdin.flush()
        
        r, _, _ = select.select([proc.stdout], [], [], 3.0)
        if not r:
            proc.kill()
            raise Exception("Timeout during handshake initialize stage.")
        init_resp_line = proc.stdout.readline()
        
        init_notif = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        proc.stdin.write(json.dumps(init_notif) + "\n")
        proc.stdin.flush()
        
        # 2. Call the tool!
        call_req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        proc.stdin.write(json.dumps(call_req) + "\n")
        proc.stdin.flush()
        
        r, _, _ = select.select([proc.stdout], [], [], 10.0) # Allow up to 10 seconds for tool execution!
        if not r:
            proc.kill()
            raise Exception(f"Timeout waiting for tool '{tool_name}' to complete execution.")
            
        call_resp_line = proc.stdout.readline()
        if not call_resp_line:
            raise Exception("Process closed stdout unexpectedly during tool execution.")
            
        call_resp = json.loads(call_resp_line)
        if "error" in call_resp:
            raise Exception(f"Tool execution returned error: {call_resp['error']}")
            
        result = call_resp.get("result", {})
        
        proc.terminate()
        try:
            proc.wait(timeout=1.0)
        except:
            proc.kill()
            
        return {
            "status": "success",
            "result": result
        }
    except Exception as e:
        if proc:
            try:
                proc.kill()
            except:
                pass
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/sessions")
async def get_sessions():
    """Returns statistics for all active sessions, optionally filtered by policy."""
    import copy
    policy = get_current_security_policy()
    if not policy:
        return GLOBAL_STATE["sessions"]
    
    filtered_sessions = copy.deepcopy(GLOBAL_STATE["sessions"])
    for sid, session in filtered_sessions.items():
        if "tools" in session and isinstance(session["tools"], list):
            session["tools"] = [
                t for t in session["tools"]
                if policy.is_action_allowed(
                    t.get("id") or t.get("name") if isinstance(t, dict) else (t.id if hasattr(t, "id") else t.name),
                    method=t.get("method") or t.get("meta", {}).get("method") if isinstance(t, dict) else (t.method if hasattr(t, "method") else (t.meta.get("method") if hasattr(t, "meta") else None))
                )["allowed"]
            ]
    return filtered_sessions

def filter_manifest_string(manifest_str: str, policy) -> str:
    if not manifest_str:
        return manifest_str
    
    # Try parsing as pure JSON first
    try:
        data = json.loads(manifest_str)
        # Filter tools
        if "tools" in data and isinstance(data["tools"], list):
            data["tools"] = [
                t for t in data["tools"]
                if policy.is_action_allowed(
                    t.get("name") or t.get("id") if isinstance(t, dict) else t.id,
                    method=t.get("method") or t.get("meta", {}).get("method") if isinstance(t, dict) else (t.meta.get("method") if hasattr(t, "meta") else None)
                )["allowed"]
            ]
        # Filter landmarks
        if "landmarks" in data:
            if isinstance(data["landmarks"], dict):
                data["landmarks"] = {
                    id: val for id, val in data["landmarks"].items()
                    if policy.is_action_allowed(
                        id,
                        method=val.get("method") or val.get("meta", {}).get("method") if isinstance(val, dict) else (val.method if hasattr(val, "method") else None)
                    )["allowed"]
                }
            elif isinstance(data["landmarks"], list):
                data["landmarks"] = [
                    lm for lm in data["landmarks"]
                    if policy.is_action_allowed(
                        lm.get("id") or lm.get("name") if isinstance(lm, dict) else lm.id,
                        method=lm.get("method") or lm.get("meta", {}).get("method") if isinstance(lm, dict) else (lm.method if hasattr(lm, "method") else None)
                    )["allowed"]
                ]
        return json.dumps(data)
    except Exception:
        # Check if it has a json-elemm block in markdown
        import re
        pattern = r"(```json-elemm\s+)([\s\S]*?)(```)"
        match = re.search(pattern, manifest_str)
        if match:
            try:
                json_part = match.group(2).strip()
                tools = json.loads(json_part)
                if isinstance(tools, list):
                    filtered_tools = [
                        t for t in tools
                        if policy.is_action_allowed(
                            t.get("name") or t.get("id") if isinstance(t, dict) else t.id,
                            method=t.get("method") or t.get("meta", {}).get("method") if isinstance(t, dict) else None
                        )["allowed"]
                    ]
                else:
                    t = tools
                    allowed = policy.is_action_allowed(
                        t.get("name") or t.get("id") if isinstance(t, dict) else t.id,
                        method=t.get("method") or t.get("meta", {}).get("method") if isinstance(t, dict) else None
                    )["allowed"]
                    filtered_tools = t if allowed else {}
                
                new_json_part = json.dumps(filtered_tools, indent=2)
                return manifest_str[:match.start(2)] + new_json_part + manifest_str[match.end(2):]
            except Exception as e:
                logger.warning(f"Failed to parse and filter embedded json-elemm block: {e}")
        return manifest_str

@app.get("/api/v1/sessions/{sid}/manifest")
async def get_session_manifest(sid: str):
    """Returns the manifest for a specific session, optionally filtered by policy."""
    manifest = GLOBAL_STATE["manifests"].get(sid)
    if not manifest:
        return {"manifest": None, "message": "No manifest found for this session"}
    
    policy = get_current_security_policy()
    if policy:
        manifest = filter_manifest_string(manifest, policy)
        
    return {"manifest": manifest}

@app.post("/api/v1/internal/publish")
async def publish_event(event: Dict[str, Any]):
    """Aggregates events and broadcasts via WebSockets."""
    sid = event.get("session_id", "default")
    action = event.get("last_action", "unknown")
    logger.debug(f"Dashboard received event: {action} [Session: {sid}]")
    
    # Ensure session exists in state
    if sid not in GLOBAL_STATE["sessions"]:
        GLOBAL_STATE["sessions"][sid] = {
            "tokens_in": 0,
            "tokens_out": 0,
            "total_tokens": 0,
            "chars_in": 0,
            "chars_out": 0,
            "total_chars": 0,
            "landmark_count": 0,
            "version": __version__,
            "last_action": "Session started",
            "last_seen": time.time(),
            "history": []
        }
    
    # Update last seen
    GLOBAL_STATE["sessions"][sid]["last_seen"] = time.time()

    # Update states
    for k, v in event.items():
        if k in ["tokens_in", "tokens_out", "chars_in", "chars_out"] and v is not None:
            # ACCUMULATE
            GLOBAL_STATE[k] += v
            GLOBAL_STATE["sessions"][sid][k] += v
        elif k in ["active_sites_count", "landmark_count", "last_action", "total_tokens", "total_chars"] and v is not None:
            # OVERWRITE
            GLOBAL_STATE[k] = v
            if k in GLOBAL_STATE["sessions"][sid]:
                GLOBAL_STATE["sessions"][sid][k] = v
            elif k == "active_sites_count":
                # Special case for site count mapping
                GLOBAL_STATE["active_sites_count"] = v
        elif k == "manifest" and v is not None:
            # Store manifest per session
            GLOBAL_STATE["manifests"][sid] = v

    # Track active URL for lazy loading
    last_action = event.get("last_action", "")
    
    # 1. Explicit connection strings
    if "Connected to" in last_action or "connect_to_site" in last_action:
        import re
        match = re.search(r'https?://[^\s\]]+', last_action)
        if match:
            GLOBAL_STATE["sessions"][sid]["active_url"] = match[0].rstrip('.')
    
    # 2. Check input parameters if available
    ev_input = event.get("input")
    if ev_input and isinstance(ev_input, dict):
        if ev_input.get("url"):
            GLOBAL_STATE["sessions"][sid]["active_url"] = ev_input["url"]
        elif ev_input.get("parameters") and isinstance(ev_input["parameters"], dict) and ev_input["parameters"].get("url"):
             GLOBAL_STATE["sessions"][sid]["active_url"] = ev_input["parameters"]["url"]
    
    # 3. Check for specific connect_to_site call in action field
    action_str = event.get("action", "")
    if "connect_to_site" in action_str:
        if ev_input and isinstance(ev_input, dict) and ev_input.get("url"):
            GLOBAL_STATE["sessions"][sid]["active_url"] = ev_input["url"]
    
    # Store in history (last 20)
    history_entry = {
        "action": event.get("last_action"),
        "input": event.get("input"),
        "output": event.get("output"),
        "status": event.get("status", "success"),
        "tokens_in": event.get("tokens_in", 0),
        "tokens_out": event.get("tokens_out", 0),
        "chars_in": event.get("chars_in", 0),
        "chars_out": event.get("chars_out", 0),
        "timestamp": event.get("timestamp"),
        "session_id": sid,
        "request_id": event.get("request_id"),
        "parent_request_id": event.get("parent_request_id"),
        "duration_ms": event.get("duration_ms"),
        "full_size": event.get("full_size")
    }
    
    if "history" not in GLOBAL_STATE: GLOBAL_STATE["history"] = []
    GLOBAL_STATE["history"].insert(0, history_entry)
    GLOBAL_STATE["history"] = GLOBAL_STATE["history"][:50]
    
    GLOBAL_STATE["sessions"][sid]["history"].insert(0, history_entry)
    GLOBAL_STATE["sessions"][sid]["history"] = GLOBAL_STATE["sessions"][sid]["history"][:50]
            
    # Also broadcast the specific event to WS, but include the TOTALS for UI
    broadcast_data = {
        **event,
        "tokens_in_total": GLOBAL_STATE["sessions"][sid]["tokens_in"],
        "tokens_out_total": GLOBAL_STATE["sessions"][sid]["tokens_out"],
        "chars_in_total": GLOBAL_STATE["sessions"][sid]["chars_in"],
        "chars_out_total": GLOBAL_STATE["sessions"][sid]["chars_out"],
        "global_tokens_in": GLOBAL_STATE["tokens_in"],
        "global_tokens_out": GLOBAL_STATE["tokens_out"],
        "global_chars_in": GLOBAL_STATE["chars_in"],
        "global_chars_out": GLOBAL_STATE["chars_out"],
        "active_clients": len([s for s in GLOBAL_STATE["sessions"].values() if time.time() - s.get("last_seen", 0) < 300]),
        "active_sites": len({s.get("active_url") for s in GLOBAL_STATE["sessions"].values() if time.time() - s.get("last_seen", 0) < 300 and s.get("active_url")})
    }
    await manager.broadcast(broadcast_data)
    return {"status": "aggregated", "session": sid}

@app.websocket("/ws/trace")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    
    # Task to send periodic status updates
    async def send_status_updates():
        try:
            while True:
                status = await get_status()
                await websocket.send_json({"type": "status_update", **status})
                await asyncio.sleep(1)
        except:
            pass

    status_task = asyncio.create_task(send_status_updates())
    
    try:
        while True:
            # Just keep the connection alive and listen for any client messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    finally:
        status_task.cancel()

@app.get("/api/v1/vault/summary")
async def get_vault_summary():
    if not os.path.exists(VAULT_PATH):
        return []

    try:
        with open(VAULT_PATH, "r") as f:
            vault = json.load(f)
            
        summary = []
        for host, data in vault.items():
            if isinstance(data, str):
                summary.append({"host": host, "type": "apiKey (legacy)", "status": "configured"})
            else:
                summary.append({
                    "host": host, 
                    "type": data.get("type", "apiKey"), 
                    "status": "configured"
                })
        return summary
    except Exception as e:
        return [{"host": "Error", "type": str(e), "status": "error"}]

# Mount static files for the frontend if the directory exists
frontend_dist_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../frontend/dist"))
if not os.path.exists(frontend_dist_path):
    # Fallback to local package dist folder if installed/packaged
    frontend_dist_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "dist"))

if os.path.exists(frontend_dist_path):
    logger.info(f"Serving frontend from {frontend_dist_path}")
    app.mount("/", StaticFiles(directory=frontend_dist_path, html=True), name="frontend")
else:
    logger.warning(f"Frontend dist directory not found at {frontend_dist_path}")


def main():
    import uvicorn
    import argparse
    
    parser = argparse.ArgumentParser(description="Start the Elemm Gateway Dashboard Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=8090, help="Port to bind the server to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    
    args = parser.parse_args()
    
    uvicorn.run("elemm_gateway.ui_backend.dashboard_server:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
