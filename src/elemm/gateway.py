import httpx
import logging
import asyncio
import json
import re
from typing import List, Dict, Any, Optional
from .mcp import LandmarkBridge
import mcp.types as types

logger = logging.getLogger("elemm-gateway")

class ElemmGateway(LandmarkBridge):
    """
    The Single-Script Gateway.
    Provides a 'connect_to_site' tool that dynamically imports tools from an Elemm .md manifest.
    """
    def __init__(self, server_name: str = "elemm-gateway"):
        # We pass None for manager to indicate gateway mode
        super().__init__(manager=None, base_url="", server_name=server_name)
        self.connected_sites = {} 
        self.active_site_url = None
        self.ctx = "root"

        # RE-REGISTER the list_tools handler to ensure our version wins
        @self.server.list_tools()
        async def handle_list_tools() -> List[types.Tool]:
            return await self._handle_list_tools()

        # RE-REGISTER the call_tool handler
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict | None) -> List[types.TextContent]:
            return await self._handle_call_tool(name, arguments or {})

    async def _handle_list_tools(self) -> List[types.Tool]:
        """Provides the 'connect' tool + any tools from the active site."""
        # 1. ALWAYS provide the connect tool
        tools = [
            types.Tool(
                name="connect_to_site",
                description="Connect to an Elemm-compliant website to discover its tools and landmarks via its .md manifest.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "The base URL of the website (e.g., http://localhost:8000)"}
                    },
                    "required": ["url"]
                }
            )
        ]

        # 2. Add site-specific tools IF connected
        if self.active_site_url and self.active_site_url in self.connected_sites:
            site_data = self.connected_sites[self.active_site_url]
            # Add native tools from the remote site
            for t_dict in site_data.get("tools", []):
                tools.append(types.Tool(**t_dict))
            
            # Add core protocol tools for the remote site
            # We get them from the base class logic but filter them appropriately
            core_tools = await super()._handle_list_tools()
            tools.extend(core_tools)
            
        return tools

    async def _handle_call_tool(self, name: str, arguments: dict) -> List[types.TextContent]:
        """Dispatches calls to 'connect' or proxied site tools."""
        if name == "connect_to_site":
            return await self._connect(arguments.get("url", ""))
        
        # If it's a core tool, use the remote-aware handler
        if name in ["get_manifest", "navigate", "inspect_landmark", "execute_action"]:
            return await self._handle_remote_core_tool(name, arguments)

        # Otherwise, proxy to the active site's execute endpoint
        return await self._execute_native_action(name, arguments)

    async def _connect(self, url: str) -> List[types.TextContent]:
        """Fetches the .md manifest and parses technical metadata."""
        url = url.rstrip("/")
        try:
            async with httpx.AsyncClient() as client:
                manifest_url = f"{url}/.well-known/elemm-manifest.md"
                resp = await client.get(manifest_url)
                if resp.status_code != 200:
                    return [types.TextContent(type="text", text=f"Failed to find Elemm manifest at {manifest_url}. Status: {resp.status_code}")]

                md_content = resp.text
                
                # Extract JSON-ELEMM block
                match = re.search(r"```json-elemm\s+(.*?)\s+```", md_content, re.DOTALL)
                tools = []
                if match:
                    try:
                        tools = json.loads(match.group(1))
                    except Exception as je:
                        logger.warning(f"Failed to parse technical metadata: {je}")

                self.connected_sites[url] = {
                    "tools": tools,
                    "manifest": md_content
                }
                self.active_site_url = url
                self.base_url = url
                
                welcome_msg = f"Successfully connected to {url}. Subsystems and tools discovered.\n\n{md_content[:500]}..."
                return [types.TextContent(type="text", text=welcome_msg)]
        except Exception as e:
            return [types.TextContent(type="text", text=f"Connection Error to {url}: {e}")]

    async def _handle_remote_core_tool(self, name: str, arguments: dict) -> List[types.TextContent]:
        """Handles navigate/inspect by talking to the remote .md endpoint."""
        if not self.active_site_url:
            return [types.TextContent(type="text", text="Error: Not connected to any site. Call connect_to_site first.")]

        try:
            async with httpx.AsyncClient() as client:
                if name == "inspect_landmark":
                    lid = arguments.get("landmark_id")
                    resp = await client.get(f"{self.active_site_url}/.well-known/elemm-manifest.md", params={"landmark_id": lid})
                    return [types.TextContent(type="text", text=resp.text)]
                elif name == "navigate":
                    self.ctx = arguments.get("landmark_id", "root")
                    return [types.TextContent(type="text", text=f"Context switched to '{self.ctx}'.")]
                elif name == "get_manifest":
                    return [types.TextContent(type="text", text=self.connected_sites[self.active_site_url]["manifest"])]
                elif name == "execute_action":
                    # For remote execution via the generic execute tool
                    aid = arguments.get("action_id")
                    params = arguments.get("parameters", {})
                    return await self._execute_native_action(aid, params)
        except Exception as e:
            return [types.TextContent(type="text", text=f"Remote Core Tool Error ({name}): {e}")]
        
        return [types.TextContent(type="text", text=f"Tool {name} not implemented for remote sites.")]

    async def _execute_native_action(self, name: str, arguments: dict) -> List[types.TextContent]:
        """Proxy call to the remote site's executor."""
        if not self.active_site_url:
            return [types.TextContent(type="text", text="Error: No active connection.")]

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.active_site_url}/.well-known/elemm/execute",
                    json={"action_id": name, "parameters": arguments}
                )
                if resp.status_code != 200:
                    try:
                        res = resp.json()
                        return [types.TextContent(type="text", text=f"Remote Error: {res.get('error', resp.text)}")]
                    except:
                        return [types.TextContent(type="text", text=f"Remote HTTP Error {resp.status_code}: {resp.text}")]
                
                res = resp.json()
                # Format result
                if isinstance(res, dict) and "text" in res:
                    return [types.TextContent(type="text", text=res["text"])]
                
                output_text = self._format_action_result(name, res, None, False)
                return [types.TextContent(type="text", text=output_text)]
        except Exception as e:
            return [types.TextContent(type="text", text=f"Proxy Error: {e}")]

    def run(self):
        """Standard MCP runner for Gateway."""
        from mcp.server.stdio import stdio_server
        async def _run():
            async with stdio_server() as (read, write):
                await self.server.run(read, write, self.server.create_initialization_options())
        asyncio.run(_run())
