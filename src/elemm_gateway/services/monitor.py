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
    
    def __init__(self, publish_url: str = None, char_to_token_ratio: float = 4.0):
        self.publish_url = publish_url or "http://127.0.0.1:8090/api/v1/internal/publish"
        self.char_to_token_ratio = char_to_token_ratio
        
    def _async_push(self, event: dict):
        """Internal helper to push events via HTTP without blocking."""
        if os.environ.get("ELEMM_SKIP_MONITOR") == "1":
            return
            
        try:
            # Use synchronous httpx client inside the thread
            with httpx.Client(timeout=2.0) as client:
                r = client.post(self.publish_url, json=event)
                if r.status_code != 200:
                    logger.warning(f"Dashboard Monitor: Server returned {r.status_code}")
        except (httpx.ConnectError, httpx.ConnectTimeout):
            # Silent fail if server is down or unreachable
            return
        except Exception as e:
            # Log other unexpected errors
            logger.error(f"Dashboard Monitor: Failed to push event to {self.publish_url}: {e}")

    @staticmethod
    def calculate_characters(data: Any) -> int:
        """Calculates raw character count of the data."""
        if data is None:
            return 0
        if isinstance(data, str):
            return len(data)
        try:
            return len(json.dumps(data, indent=None))
        except:
            return len(str(data))

    def estimate_tokens(self, data: Any, is_input: bool = False, ratio: float = None) -> int:
        """
        Estimates token count based on character count and ratio.
        """
        if data is None:
            return 0
            
        char_count = self.calculate_characters(data)
        
        # Pure numbers: no fixed overhead unless specified in config/parameters
        base_cost = 0
        
        actual_ratio = ratio or self.char_to_token_ratio
        payload_cost = int(char_count / actual_ratio)
        
        return base_cost + payload_cost

    def report_activity(self, 
                       active_sites: int = None, 
                       total_tokens: int = None, 
                       last_action: str = None,
                       landmark_count: int = None,
                       tokens_in: int = None,
                       tokens_out: int = None,
                       chars_in: int = None,
                       chars_out: int = None,
                       session_id: str = "default",
                       input_data: Any = None,
                       output_data: Any = None,
                       status: str = "success",
                       manifest: str = None,
                       **kwargs):
        """
        Broadcasts activity to the dashboard server.
        """
        # Auto-calculate characters if not provided
        if chars_in is None and input_data is not None:
            chars_in = self.calculate_characters(input_data)
        if chars_out is None and output_data is not None:
            chars_out = self.calculate_characters(output_data)

        # Auto-calculate tokens if not provided
        if tokens_in is None and input_data is not None:
            tokens_in = self.estimate_tokens(input_data, is_input=True)
        if tokens_out is None and output_data is not None:
            tokens_out = self.estimate_tokens(output_data, is_input=False)

        # Safety: Truncate large data for the UI (increased to 500k for high-fidelity developer console)
        def truncate(data, limit=500000):
            try:
                s = json.dumps(data, indent=None) if not isinstance(data, str) else data
            except:
                s = str(data)
            return (s[:limit] + '...') if len(s) > limit else s

        # Ensure we always have integers for metrics
        c_in = int(chars_in) if chars_in is not None else 0
        c_out = int(chars_out) if chars_out is not None else 0
        t_in = int(tokens_in) if tokens_in is not None else 0
        t_out = int(tokens_out) if tokens_out is not None else 0

        event = {
            "type": "activity",
            "active_sites_count": active_sites,
            "total_tokens": total_tokens,
            "last_action": last_action,
            "landmark_count": landmark_count,
            "tokens_in": t_in,
            "tokens_out": t_out,
            "chars_in": c_in,
            "chars_out": c_out,
            "session_id": session_id,
            "input": truncate(input_data) if input_data is not None else None,
            "output": truncate(output_data) if output_data is not None else None,
            "manifest": truncate(manifest, limit=500000) if manifest else None,
            "status": kwargs.get("status", status),
            "timestamp": time.time(),
            "request_id": kwargs.get("request_id"),
            "parent_request_id": kwargs.get("parent_request_id"),
            "duration_ms": kwargs.get("duration_ms"),
            "full_size": kwargs.get("full_size") or c_out
        }
        
        # Always push in background to keep core fast
        Thread(target=self._async_push, args=(event,)).start()

_monitor = None

def get_monitor() -> DashboardMonitor:
    global _monitor
    if _monitor is None:
        _monitor = DashboardMonitor()
    return _monitor
