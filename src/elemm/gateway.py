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
        # Initial context is empty
        super().__init__(manager=None, base_url="", server_name=server_name)
        self.connected_sites = {} # url -> {tools, manifest_md}
        self.active_site_url = None

    async def _handle_list_tools(self) -> List[types.Tool]:
        """Provides the 'connect' tool + any tools from the active site."""
        # 1. Start with the core 'connect' tool
        tools = [
            types.Tool(
                name="connect_to_site",
                description="Connect to an Elemm-compliant website to discover its tools and landmarks via its .md manifest.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "The base URL of the website (e.g., https://myshop.ai)"}
                    },
                    "required": ["url"]
                }
            )
        ]

        # 2. Add tools from the active site if connected
        if self.active_site_url and self.active_site_url in self.connected_sites:
            site_data = self.connected_sites[self.active_site_url]
            # Add site tools
            for t_dict in site_data.get("tools", []):
                tools.append(types.Tool(**t_dict))
            
            # Also add core protocol tools (inspect, navigate) for this site
            # We override them to work with the active site
            tools.extend(await super()._handle_list_tools())
            
        return tools

    async def _handle_call_tool(self, name: str, arguments: dict) -> List[types.TextContent]:
        """Dispatches calls to 'connect' or proxied site tools."""
        if name == "connect_to_site":
            return await self._connect(arguments.get("url", ""))
        
        # If it's a core tool (navigate, inspect_landmark), super() handles it 
        # BUT it needs self.manager which is None. So we must override them.
        if name in ["get_manifest", "navigate", "inspect_landmark"]:
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
                    return [types.TextContent(type="text", text=f"Failed to find Elemm manifest at {manifest_url}")]

                md_content = resp.text
                
                # Extract JSON-ELEMM block
                # Looking for ```json-elemm ... ```
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
                # Update base_url for proxying
                self.base_url = url
                
                welcome_msg = f"Successfully connected to {url}.\n\n{md_content[:500]}..."
                return [types.TextContent(type="text", text=welcome_msg)]
        except Exception as e:
            return [types.TextContent(type="text", text=f"Connection Error: {e}")]

    async def _handle_remote_core_tool(self, name: str, arguments: dict) -> List[types.TextContent]:
        """Handles navigate/inspect by talking to the remote .md endpoint."""
        if not self.active_site_url:
            return [types.TextContent(type="text", text="Error: Not connected to any site.")]

        try:
            async with httpx.AsyncClient() as client:
                if name == "inspect_landmark":
                    lid = arguments.get("landmark_id")
                    resp = await client.get(f"{self.active_site_url}/.well-known/elemm-manifest.md", params={"landmark_id": lid})
                    return [types.TextContent(type="text", text=resp.text)]
                elif name == "navigate":
                    self.ctx = arguments.get("landmark_id", "root")
                    return [types.TextContent(type="text", text=f"Context switched to '{self.ctx}'. Call list_tools to see updated toolset.")]
                elif name == "get_manifest":
                    return [types.TextContent(type="text", text=self.connected_sites[self.active_site_url]["manifest"])]
        except Exception as e:
            return [types.TextContent(type="text", text=f"Remote Core Tool Error: {e}")]
        
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
                res = resp.json()
                if resp.status_code != 200:
                    return [types.TextContent(type="text", text=f"Remote Error: {res.get('error', resp.text)}")]
                
                # Format result
                if isinstance(res, dict) and "text" in res:
                    return [types.TextContent(type="text", text=res["text"])]
                
                output_text = self._format_action_result(name, res, None, False)
                return [types.TextContent(type="text", text=output_text)]
        except Exception as e:
            return [types.TextContent(type="text", text=f"Proxy Error: {e}")]
