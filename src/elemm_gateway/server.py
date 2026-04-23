# This file is part of Elemm.
#
# Elemm is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Elemm is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Elemm.  If not, see <https://www.gnu.org/licenses/>.

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
        self.session_headers = {} # Ensure persistence store exists

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
        core_tools = await super()._handle_list_tools()
        tools.extend(core_tools)

        # 3. Add Remote Technical Tools (if connected)
        if self.active_site_url:
            remote_info = self.connected_sites.get(self.active_site_url, {})
            remote_tools = remote_info.get("tools", [])
            for t_dict in remote_tools:
                tools.append(types.Tool(**t_dict))
            
        return tools

    async def _handle_call_tool(self, name: str, arguments: dict) -> List[types.TextContent]:
        """Dispatches calls to 'connect' or proxied core tools."""
        if name == "connect_to_site":
            return await self._connect(arguments.get("url", ""))
        
        # Dispatch to remote-aware core handlers
        if name in ["get_manifest", "navigate", "execute_action", "inspect_landmark"]:
            return await self._handle_remote_core_tool(name, arguments)

        # 3. Dynamic Proxy: If it's a known remote tool, execute it via execute_action proxy
        if self.active_site_url:
            remote_info = self.connected_sites.get(self.active_site_url, {})
            remote_tools = remote_info.get("tools", [])
            if any(t.get("name") == name for t in remote_tools):
                # Proxy the call
                return await self._handle_remote_core_tool("execute_action", {
                    "action_id": name,
                    "parameters": arguments
                })

        return [types.TextContent(type="text", text=f"Error: Tool '{name}' not found. Use 'connect_to_site' first.")]

    async def _connect(self, url: str) -> List[types.TextContent]:
        """Fetches the .md manifest and establishes the session."""
        url = url.rstrip("/")
        try:
            async with httpx.AsyncClient() as client:
                manifest_url = f"{url}/.well-known/elemm-manifest.md"
                # Request with technical=true to get the json-elemm block
                resp = await client.get(manifest_url, params={"technical": "true"})
                if resp.status_code != 200:
                    return [types.TextContent(type="text", text=f"Failed to find Elemm manifest at {manifest_url}. Status: {resp.status_code}")]

                # Semantic Manifest for the Agent
                md_content = resp.text
                
                # Simple extraction for directive
                def get_section(name):
                    pattern = rf"^### {name}\s*\n(.*?)(?=\n###|\n##|$)"
                    m = re.search(pattern, md_content, re.MULTILINE | re.DOTALL)
                    return m.group(1).strip() if m else None

                directive = get_section("AGENT DIRECTIVE") or "Execute tasks according to the available tools."

                # Extract Technical Tools from json-elemm block
                mcp_tools = []
                json_match = re.search(r"```json-elemm\n(.*?)\n```", md_content, re.DOTALL)
                if json_match:
                    try:
                        mcp_tools = json.loads(json_match.group(1))
                        logger.info(f"Gateway: Discovered {len(mcp_tools)} technical tools via json-elemm.")
                    except Exception as e:
                        logger.warning(f"Gateway: Failed to parse json-elemm block: {e}")

                self.connected_sites[url] = {
                    "manifest": md_content,
                    "tools": mcp_tools
                }
                self.active_site_url = url
                
                welcome_msg = (
                    f"Connected to {url} successfully.\n\n"
                    f"Instructions: {directive}\n\n"
                    f"Discovered {len(mcp_tools)} tools. Use get_manifest or navigation tools to explore the site."
                )
                return [types.TextContent(type="text", text=welcome_msg)]
        except Exception as e:
            return [types.TextContent(type="text", text=f"Connection Error: {e}")]

    async def _handle_remote_core_tool(self, name: str, arguments: dict) -> List[types.TextContent]:
        """Proxy for the 4 core protocol tools."""
        if not self.active_site_url:
            return [types.TextContent(type="text", text="Error: Not connected. Call 'connect_to_site' first.")]

        # Sync context for potential internal dependencies
        from elemm.core.context import session_headers
        token_ctx = session_headers.set(self.session_headers)

        try:
            async with httpx.AsyncClient() as client:
                if name == "get_manifest":
                    raw_md = self.connected_sites[self.active_site_url]["manifest"]
                    # Token Optimization: Strip the technical json-elemm block for the agent
                    clean_md = re.sub(r"\n---\n### Technical Discovery.*```json-elemm.*?```", "", raw_md, flags=re.DOTALL)
                    return [types.TextContent(type="text", text=clean_md.strip())]
                
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
                    
                    # Scoped Auth: Get headers for this specific host
                    from urllib.parse import urlparse
                    host_key = urlparse(self.active_site_url).netloc
                    current_headers = self.session_headers.get(host_key, {})
                    
                    if current_headers:
                        logger.debug(f"Gateway: Injecting auth headers for {host_key}")

                    resp = await client.post(
                        f"{self.active_site_url}/.well-known/elemm/execute",
                        json={"action_id": aid, "parameters": params},
                        headers=current_headers
                    )
                    
                    if resp.status_code != 200:
                        logger.error(f"Gateway: Remote Error {resp.status_code} for {aid}")
                        return [types.TextContent(type="text", text=f"Remote Error ({resp.status_code}): {resp.text}")]
                    
                    res = resp.json()

                    # Auto-Capture Auth Tokens from Remote Result
                    if isinstance(res, dict) and "access_token" in res:
                        new_token = res["access_token"]
                        host_headers = self.session_headers.get(host_key, {}).copy()
                        host_headers["Authorization"] = f"Bearer {new_token}"
                        self.session_headers[host_key] = host_headers
                        logger.info(f"Gateway: Auto-captured access_token for host '{host_key}'")

                    # We use the base class stringifier for consistency
                    output_text = self._stringify_result(res)
                    return [types.TextContent(type="text", text=f"### RESULT: {aid}\n{output_text}")]

        except Exception as e:
            logger.error(f"Gateway Proxy Error: {e}")
            return [types.TextContent(type="text", text=f"Proxy Error ({name}): {e}")]
        finally:
            session_headers.reset(token_ctx)
        
        return [types.TextContent(type="text", text=f"Tool {name} not implemented for remote sites.")]

    def run(self):
        """Standard MCP runner for Gateway."""
        from mcp.server.stdio import stdio_server
        async def _run():
            async with stdio_server() as (read, write):
                await self.server.run(read, write, self.server.create_initialization_options())
        asyncio.run(_run())
