from typing import Dict, Optional, Union
from fastapi import FastAPI, Request
import httpx
import logging

logger = logging.getLogger(__name__)

def bind_mcp_sse(manager, app: FastAPI, route_prefix: str = "/mcp"):
    """
    Exposes the landmark protocol as an MCP SSE endpoint with session isolation.
    """
    from mcp.server.sse import SseServerTransport
    from .mcp import LandmarkBridge
    
    # We use a dictionary to store isolated bridges per session
    # In a production environment, this should have a TTL or cleanup mechanism
    sse_transport = SseServerTransport(f"{route_prefix}/messages")

    @app.get(f"{route_prefix}/sse", include_in_schema=False)
    async def handle_sse(request: Request):
        # Each connection gets its own bridge instance for true isolation
        bridge = LandmarkBridge(manager=manager)
        
        async with sse_transport.connect_sse(request.scope, request.receive, request._send) as (read, write):
            await bridge.server.run(read, write, bridge.server.create_initialization_options())

    @app.post(f"{route_prefix}/messages", include_in_schema=False)
    async def handle_messages(request: Request):
        await sse_transport.handle_post_request(request.scope, request.receive, request.send)

def run_mcp_stdio(manager, app_import_path: str, host: str = "127.0.0.1", port: int = 8001):
    """
    Dual-Boot Launcher: Starts Web server and then runs MCP Stdio in main thread.
    """
    import threading
    import uvicorn
    import time
    from .mcp import LandmarkBridge

    # Start Web server in background
    def start_web():
        uvicorn.run(app_import_path, host=host, port=port, log_level="error")
    
    t = threading.Thread(target=start_web, daemon=True)
    t.start()
    
    # Wait for boot
    time.sleep(2)
    
    # Start Bridge (Local mode)
    bridge = LandmarkBridge(manager=manager, base_url=f"http://{host}:{port}")
    bridge.run_stdio()
