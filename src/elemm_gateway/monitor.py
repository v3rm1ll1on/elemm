# Copyright (C) 2026 Marc Stöcker
# Part of Elemm v1.2.0 - Telemetry & Monitoring Module

import os
import json
import time
import logging
import httpx
from typing import List, Dict, Any
from threading import Thread

logger = logging.getLogger(__name__)

class DashboardMonitor:
    """
    Central monitoring class for the Elemm Gateway Dashboard.
    Pushes telemetry data directly to the dashboard server.
    Uses httpx for better performance and consistency.
    """
    
    def __init__(self, publish_url: str = None):
        self.publish_url = publish_url or "http://127.0.0.1:8090/api/v1/internal/publish"
        
    def _async_push(self, event: dict):
        """Internal helper to push events via HTTP without blocking."""
        try:
            # Use synchronous httpx client inside the thread
            with httpx.Client(timeout=2.0) as client:
                r = client.post(self.publish_url, json=event)
                if r.status_code != 200:
                    logger.warning(f"Dashboard Monitor: Server returned {r.status_code}")
        except Exception as e:
            # Log the error so we can see it in the server console
            print(f"DEBUG: Dashboard Monitor Push Failed: {e}")
            logger.error(f"Dashboard Monitor: Failed to push event to {self.publish_url}: {e}")

    @staticmethod
    def estimate_tokens(data: Any, is_input: bool = False) -> int:
        """
        Estimates token count with realistic LLM overhead.
        - Base overhead for a tool call: ~40-60 tokens
        - Payload: 4 chars per token
        """
        if data is None:
            return 0
            
        # Base cost for the tool call structure (name, syntax)
        base_cost = 45 if is_input else 15 
        
        payload_str = json.dumps(data) if not isinstance(data, str) else data
        payload_cost = len(payload_str) // 4
        
        return base_cost + payload_cost

    def report_activity(self, 
                       active_sites: int = None, 
                       total_tokens: int = None, 
                       last_action: str = None,
                       landmark_count: int = None,
                       tokens_in: int = None,
                       tokens_out: int = None,
                       session_id: str = "default",
                       input_data: Any = None,
                       output_data: Any = None,
                       status: str = "success",
                       manifest: str = None,
                       **kwargs):
        """
        Broadcasts activity to the dashboard server.
        """
        # Auto-calculate tokens if not provided
        if tokens_in is None and input_data is not None:
            tokens_in = self.estimate_tokens(input_data, is_input=True)
        if tokens_out is None and output_data is not None:
            tokens_out = self.estimate_tokens(output_data, is_input=False)

        # Safety: Truncate large data for the UI
        def truncate(data, limit=10000):
            try:
                s = json.dumps(data, indent=None) if not isinstance(data, str) else data
            except:
                s = str(data)
            return (s[:limit] + '...') if len(s) > limit else s

        event = {
            "type": "activity",
            "active_sites_count": active_sites,
            "total_tokens": total_tokens,
            "last_action": last_action,
            "landmark_count": landmark_count,
            "tokens_in": tokens_in or 0,
            "tokens_out": tokens_out or 0,
            "session_id": session_id,
            "input": truncate(input_data) if input_data is not None else None,
            "output": truncate(output_data) if output_data is not None else None,
            "manifest": truncate(manifest, limit=500000) if manifest else None,
            "status": kwargs.get("status", status),
            "timestamp": time.time(),
            "request_id": kwargs.get("request_id"),
            "parent_request_id": kwargs.get("parent_request_id"),
            "duration_ms": kwargs.get("duration_ms"),
            "full_size": kwargs.get("full_size")
        }
        # Filter None
        clean_event = {k: v for k, v in event.items() if v is not None}
        
        # Always push in background to keep core fast
        Thread(target=self._async_push, args=(clean_event,)).start()

_monitor = None

def get_monitor() -> DashboardMonitor:
    global _monitor
    if _monitor is None:
        _monitor = DashboardMonitor()
    return _monitor
