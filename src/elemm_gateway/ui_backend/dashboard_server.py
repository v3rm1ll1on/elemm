# Copyright (C) 2026 Marc Stöcker
# Part of Elemm v1.2.0 - Dashboard Backend Module

import os
import json
import time
import asyncio
import logging
import sys
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any

# Ensure project root is in path for absolute imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

# Internal Elemm Imports
from elemm_gateway.manifest_service import ManifestService
from elemm_gateway.components import VaultManager

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
    "version": "1.2.0-alpha",
    "status": "online",
    "sessions": {}, # Session-specific stats
    "manifests": {} # session_id -> manifest string
}

# Boot time for Uptime calc
START_TIME = time.time()

vault_manager = VaultManager(VAULT_PATH)

@app.get("/api/v1/inspect")
async def inspect_site(url: str, landmark_id: str = None, session_id: str = "default"):
    """
    Lazy-loads a manifest for a given URL by importing the gateway logic.
    """
    try:
        # Reload vault before inspection before inspection to get latest keys
        vault_manager.vault = vault_manager.load()
        
        result = await ManifestService.inspect_url(url, landmark_id=landmark_id, vault_manager=vault_manager)
        if result["status"] == "success":
            # Store it for the UI
            GLOBAL_STATE["manifests"][session_id] = result["manifest"]
            return result
        else:
            raise HTTPException(status_code=400, detail=result["message"])
    except Exception as e:
        logger.error(f"Inspect failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/inspect/landmark")
async def inspect_landmark(landmark_id: str, url: str = None, session_id: str = "default"):
    """
    Fetches the technical signature for a specific landmark.
    """
    if not url:
        session = GLOBAL_STATE["sessions"].get(session_id)
        if session:
            url = session.get("active_url")
    
    if not url:
        raise HTTPException(status_code=400, detail="No active URL found for this session. Please connect first.")

    try:
        # Reload vault before inspection
        vault_manager.vault = vault_manager.load()
        
        result = await ManifestService.inspect_landmark(url, landmark_id, vault_manager=vault_manager)
        return result
    except Exception as e:
        logger.error(f"Landmark inspect failed: {e}")
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
    
    return {
        **GLOBAL_STATE,
        "uptime": get_uptime(),
        "security_level": level,
        "active_clients": active_clients
    }

@app.post("/api/v1/reset")
async def reset_dashboard():
    """Clears history only, preserving global counters and sessions."""
    GLOBAL_STATE["last_action"] = "History Cleared"
    
    # Clear all history and all session entries
    GLOBAL_STATE["history"] = []
    GLOBAL_STATE["sessions"] = {}
    
    return {"status": "success", "message": "All sessions and history cleared. Global counters preserved."}

CONFIG_PATH = os.path.expanduser("~/.elemm/config.json")

@app.get("/api/v1/config")
async def get_config():
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
        return {
            "security": {"disallowed_patterns": [], "disallowed_landmarks": [], "allowed_methods": []},
            "limit_standard": 5000, "limit_inspect": 20000, "timeout_seconds": 30,
            "retry_attempts": 3, "retry_delay_ms": 1000
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
    try:
        os.makedirs(os.path.dirname(VAULT_PATH), exist_ok=True)
        with open(VAULT_PATH, "w") as f:
            json.dump(vault, f, indent=2)
        return {"status": "success", "message": "Vault updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/sessions")
async def get_sessions():
    """Returns statistics for all active sessions."""
    return GLOBAL_STATE["sessions"]

@app.get("/api/v1/sessions/{sid}/manifest")
async def get_session_manifest(sid: str):
    """Returns the manifest for a specific session."""
    manifest = GLOBAL_STATE["manifests"].get(sid)
    if not manifest:
        return {"manifest": None, "message": "No manifest found for this session"}
    return {"manifest": manifest}

@app.post("/api/v1/internal/publish")
async def publish_event(event: Dict[str, Any]):
    """Aggregates events and broadcasts via WebSockets."""
    sid = event.get("session_id", "default")
    action = event.get("last_action", "unknown")
    print(f"DEBUG: Dashboard received event: {action} [Session: {sid}]")
    
    # Ensure session exists in state
    if sid not in GLOBAL_STATE["sessions"]:
        GLOBAL_STATE["sessions"][sid] = {
            "tokens_in": 0,
            "tokens_out": 0,
            "total_tokens": 0,
            "landmark_count": 0,
            "version": "1.0.0",
            "last_action": "Session started",
            "last_seen": time.time(),
            "history": []
        }
    
    # Update last seen
    GLOBAL_STATE["sessions"][sid]["last_seen"] = time.time()

    # Update states
    for k, v in event.items():
        if k in ["tokens_in", "tokens_out"] and v is not None:
            # ACCUMULATE
            GLOBAL_STATE[k] += v
            GLOBAL_STATE["sessions"][sid][k] += v
        elif k in ["active_sites_count", "landmark_count", "last_action", "total_tokens"] and v is not None:
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
        "global_tokens_in": GLOBAL_STATE["tokens_in"],
        "global_tokens_out": GLOBAL_STATE["tokens_out"],
        "active_clients": len([s for s in GLOBAL_STATE["sessions"].values() if time.time() - s.get("last_seen", 0) < 300]),
        "active_sites": GLOBAL_STATE["active_sites_count"]
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

if __name__ == "__main__":
    import uvicorn
    # Start with reload enabled
    uvicorn.run("elemm_gateway.ui_backend.dashboard_server:app", host="127.0.0.1", port=8090, reload=True)
