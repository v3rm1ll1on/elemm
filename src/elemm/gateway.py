import httpx
import logging
import asyncio
import json
from typing import List, Dict, Any, Optional
from .mcp import LandmarkBridge
import mcp.types as types

logger = logging.getLogger("elemm-gateway")

class ElemmGateway(LandmarkBridge):
    """
    Remote Gateway for the Elemm Protocol.
    Allows connecting to ANY Elemm-compliant website and mounting it as an MCP server.
    """
    def __init__(self, target_url: str, server_name: Optional[str] = None):
        # Normalize target URL
        self.target_url = target_url.rstrip("/")
        name = server_name or f"gateway-{self.target_url.split('//')[-1].replace('.', '-')}"
        
        super().__init__(manager=None, base_url=self.target_url, server_name=name)
        self.ctx = "root"

    async def _handle_get_manifest(self, _name: str, _args: dict) -> List[types.TextContent]:
        """Fetch the Markdown manifest from the remote site."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.target_url}/.well-known/elemm-manifest.md")
                if resp.status_code == 200:
                    return [types.TextContent(type="text", text=resp.text)]
                
                # Fallback to JSON if MD is not available (Legacy support)
                resp = await client.get(f"{self.target_url}/.well-known/llm-landmarks.json")
                return [types.TextContent(type="text", text=f"Markdown manifest not found. Raw JSON:\n{resp.text}")]
        except Exception as e:
            return [types.TextContent(type="text", text=f"Gateway Error: Failed to fetch manifest from {self.target_url}. {e}")]

    async def _handle_list_tools(self) -> List[types.Tool]:
        """Fetch remote tools and combine with core protocol tools."""
        # Start with core tools (get_manifest, navigate, etc.)
        tools = await super()._handle_list_tools()
        
        try:
            async with httpx.AsyncClient() as client:
                # Fetch remote MCP tool definitions for the current context
                resp = await client.get(
                    f"{self.target_url}/.well-known/mcp-tools.json",
                    params={"group": self.ctx}
                )
                if resp.status_code == 200:
                    remote_tools = resp.json()
                    for t_dict in remote_tools:
                        tools.append(types.Tool(**t_dict))
        except Exception as e:
            logger.error(f"Gateway failed to fetch remote tools: {e}")
            
        return tools

    async def _handle_inspect_landmark(self, _name: str, arguments: dict) -> List[types.TextContent]:
        landmark_id = arguments.get("landmark_id", "")
        if not landmark_id:
            return [types.TextContent(type="text", text="Error: Missing 'landmark_id'.")]

        try:
            async with httpx.AsyncClient() as client:
                # Ask the remote site for a detailed landmark view
                resp = await client.get(
                    f"{self.target_url}/.well-known/elemm-manifest.md", 
                    params={"landmark_id": landmark_id}
                )
                return [types.TextContent(type="text", text=resp.text)]
        except Exception as e:
            return [types.TextContent(type="text", text=f"Gateway Error: {e}")]

    async def _execute_native_action(self, name: str, arguments: dict) -> List[types.TextContent]:
        """Proxy tool calls to the remote Elemm API using the universal executor."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.target_url}/.well-known/elemm/execute",
                    json={
                        "action_id": name,
                        "parameters": arguments
                    }
                )
                
                if resp.status_code != 200:
                    error_data = resp.json() if resp.status_code == 400 else {"error": resp.text}
                    return [types.TextContent(type="text", text=f"Remote Execution Error: {error_data.get('error')}")]

                # Format the result
                res = resp.json()
                # In gateway mode, we just pass back what the remote formatted for us
                # The remote server is responsible for instructions/remedies in the text
                if isinstance(res, dict) and "text" in res:
                     return [types.TextContent(type="text", text=res["text"])]
                
                # If it's raw data, we use our local formatter
                output_text = self._format_action_result(name, res, None, False)
                return [types.TextContent(type="text", text=output_text)]
        except Exception as e:
            return [types.TextContent(type="text", text=f"Gateway Proxy Error: {e}")]

    def run(self):
        """Standard MCP runner for Gateway."""
        from mcp.server.stdio import stdio_server
        async def _run():
            async with stdio_server() as (read, write):
                await self.server.run(read, write, self.server.create_initialization_options())
        asyncio.run(_run())
