import httpx
import logging
import asyncio
import json
import re
from typing import List, Dict, Any, Optional
from elemm.mcp import LandmarkBridge
import mcp.types as types

logger = logging.getLogger("elemm-gateway")

class ElemmGateway(LandmarkBridge):
    """
    The Specialized Elemm Gateway.
    Acts as a universal broker for any Elemm-compliant site.
    Provides: connect_to_site + Core Protocol Tools (proxied).
    """
    def __init__(self, server_name: str = "elemm-gateway"):
        # No local manager, we are a broker
        super().__init__(manager=None, base_url="", server_name=server_name)
        self.connected_sites = {} 
        self.active_site_url = None
        self.ctx = "root"

        # Explicitly register the connect tool
        @self.server.list_tools()
        async def handle_list_tools() -> List[types.Tool]:
            return await self._handle_list_tools()

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict | None) -> List[types.TextContent]:
            return await self._handle_call_tool(name, arguments or {})

    async def _handle_list_tools(self) -> List[types.Tool]:
        """Tools: connect_to_site + Core Elemm Tools."""
        # 1. Connect Tool
        tools = [
            types.Tool(
                name="connect_to_site",
                description="Connect to an Elemm-compliant website to discover its tools and landmarks via its .md manifest.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "The base URL of the website (e.g., http://localhost:8001)"}
                    },
                    "required": ["url"]
                }
            )
        ]

        # 2. Add Core Elemm Tools (inherited from LandmarkBridge logic)
        # These are always available and act as proxies once connected
        core_tools = await super()._handle_list_tools()
        tools.extend(core_tools)
            
        return tools

    async def _handle_call_tool(self, name: str, arguments: dict) -> List[types.TextContent]:
        """Dispatches calls to 'connect' or proxied core tools."""
        if name == "connect_to_site":
            return await self._connect(arguments.get("url", ""))
        
        # Dispatch to remote-aware core handlers
        if name in ["get_manifest", "navigate", "execute_action", "inspect_landmark"]:
            return await self._handle_remote_core_tool(name, arguments)

        return [types.TextContent(type="text", text=f"Error: Tool '{name}' not found. Use 'connect_to_site' first.")]

    async def _connect(self, url: str) -> List[types.TextContent]:
        """Fetches the .md manifest and establishes the session."""
        url = url.rstrip("/")
        try:
            async with httpx.AsyncClient() as client:
                manifest_url = f"{url}/.well-known/elemm-manifest.md"
                resp = await client.get(manifest_url)
                if resp.status_code != 200:
                    return [types.TextContent(type="text", text=f"Failed to find Elemm manifest at {manifest_url}. Status: {resp.status_code}")]

                md_content = resp.text
                
                # Discovery of technical tools (just for the agent's info)
                match = re.search(r"```json-elemm\s+(.*?)\s+```", md_content, re.DOTALL)
                tools_info = []
                if match:
                    try:
                        tools_info = json.loads(match.group(1))
                    except Exception as je:
                        logger.warning(f"Failed to parse technical metadata: {je}")

                self.connected_sites[url] = {
                    "manifest": md_content,
                    "tools": tools_info
                }
                self.active_site_url = url
                
                tool_list_str = ", ".join([t.get("name") for t in tools_info]) if tools_info else "No functional tools found."
                
                welcome_msg = (
                    f"✅ Successfully connected to {url}.\n\n"
                    f"**Discovered Tools**: {tool_list_str}\n\n"
                    f"**Instructions**:\n{md_content[:500]}...\n\n"
                    f"PROTIP: You can now use `get_manifest`, `navigate`, and `execute_action` to interact with this site."
                )
                return [types.TextContent(type="text", text=welcome_msg)]
        except Exception as e:
            return [types.TextContent(type="text", text=f"Connection Error: {e}")]

    async def _handle_remote_core_tool(self, name: str, arguments: dict) -> List[types.TextContent]:
        """Proxy for the 4 core protocol tools."""
        if not self.active_site_url:
            return [types.TextContent(type="text", text="Error: Not connected. Call 'connect_to_site' first.")]

        try:
            async with httpx.AsyncClient() as client:
                if name == "get_manifest":
                    return [types.TextContent(type="text", text=self.connected_sites[self.active_site_url]["manifest"])]
                
                if name == "inspect_landmark":
                    lid = arguments.get("landmark_id")
                    resp = await client.get(f"{self.active_site_url}/.well-known/elemm-manifest.md", params={"landmark_id": lid})
                    return [types.TextContent(type="text", text=resp.text)]
                
                if name == "navigate":
                    # We just update local context, but the real magic is in the remote Post
                    self.ctx = arguments.get("landmark_id", "root")
                    return [types.TextContent(type="text", text=f"Context switched to '{self.ctx}'.")]

                if name == "execute_action":
                    aid = arguments.get("action_id")
                    params = arguments.get("parameters", {})
                    resp = await client.post(
                        f"{self.active_site_url}/.well-known/elemm/execute",
                        json={"action_id": aid, "parameters": params}
                    )
                    if resp.status_code != 200:
                        return [types.TextContent(type="text", text=f"Remote Error ({resp.status_code}): {resp.text}")]
                    
                    res = resp.json()
                    # We use the base class stringifier for consistency
                    output_text = self._stringify_result(res)
                    return [types.TextContent(type="text", text=f"### RESULT: {aid}\n{output_text}")]

        except Exception as e:
            return [types.TextContent(type="text", text=f"Proxy Error ({name}): {e}")]
        
        return [types.TextContent(type="text", text=f"Tool {name} not implemented for remote sites.")]

    def run(self):
        """Standard MCP runner for Gateway."""
        from mcp.server.stdio import stdio_server
        async def _run():
            async with stdio_server() as (read, write):
                await self.server.run(read, write, self.server.create_initialization_options())
        asyncio.run(_run())
