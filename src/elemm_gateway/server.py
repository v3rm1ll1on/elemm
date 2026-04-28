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
from urllib.parse import urlparse

logger = logging.getLogger("elemm-gateway")

class ElemmGateway(LandmarkBridge):
    """
    The Specialized Elemm Gateway.
    Acts as a universal broker for any Elemm-compliant site.
    Provides: connect_to_site + Core Protocol Tools (proxied).
    """
    
    # Pre-compiled regex for manifest sections
    SECTION_PATTERN = re.compile(r"### (?:AGENT )?DIRECTIVE\s*\n(.*?)(?=\n###|\n##|---|$)", re.DOTALL)
    JSON_BLOCK_PATTERN = re.compile(r"```json-elemm\n(.*?)\n```", re.DOTALL)
    CLEAN_MD_PATTERN = re.compile(r"\n---\n### Technical Discovery.*```json-elemm.*?```", re.DOTALL)

    def __init__(self, server_name: str = "elemm-gateway"):
        # No local manager, we are a broker
        super().__init__(manager=None, base_url="", server_name=server_name)
        self.connected_sites = {} 
        self.active_site_url = None
        self.ctx = "root"
        self.session_headers = {} 

        # Explicitly register the connect tool and overrides
        @self.server.list_tools()
        async def handle_list_tools() -> List[types.Tool]:
            return await self._handle_list_tools()

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict | None) -> List[types.TextContent]:
            return await self._handle_call_tool(name, arguments or {})

    async def _handle_list_tools(self) -> List[types.Tool]:
        """Tools: connect_to_site + Core Elemm Tools + Remote Discovery."""
        tools = [
            types.Tool(
                name="connect_to_site",
                description="Connect to an Elemm-compliant website via its base URL. Call this FIRST if the user provides a URL or asks for site-specific actions (like booking, searching, etc.).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "Base URL (e.g., http://localhost:8001)"}
                    },
                    "required": ["url"]
                }
            ),
            types.Tool(
                name="get_landmarks",
                description="Get the map of namespaces (landmarks) from the remote site.",
                inputSchema={"type": "object", "properties": {}}
            ),
            types.Tool(
                name="get_manifest",
                description="Get the FULL manifest from the remote site.",
                inputSchema={"type": "object", "properties": {}}
            ),
            types.Tool(
                name="inspect_landmark",
                description="Get details for one or more landmarks on the remote site.",
                inputSchema={
                    "type": "object", 
                    "properties": {
                        "landmark_id": {
                            "oneOf": [
                                {"type": "string"},
                                {"type": "array", "items": {"type": "string"}}
                            ],
                            "description": "The ID or list of IDs for the landmarks to inspect."
                        }
                    },
                    "required": ["landmark_id"]
                }
            ),
            types.Tool(
                name="execute_sequence",
                description=(
                    "Execute a chain of tools in one turn. Use for multi-step tasks (Search -> Action).\n"
                    "PIPING: Use $alias.field or $index.field (e.g., $offices[0].id).\n"
                    "EXAMPLE: {actions: [\n"
                    "  {action: 'search_tool', alias: 'res', parameters: {q: 'query'}},\n"
                    "  {action: 'action_tool', parameters: {id: '$res[0].id'}}\n"
                    "]}"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "actions": {
                            "type": "array", 
                            "items": {
                                "type": "object",
                                "properties": {
                                    "action": {"type": "string"},
                                    "alias": {"type": "string", "description": "Optional name for result piping."},
                                    "parameters": {"type": "object"}
                                },
                                "required": ["action"]
                            }
                        }
                    },
                    "required": ["actions"]
                }
            )
        ]

        return tools

    async def _handle_call_tool(self, name: str, arguments: dict) -> List[types.TextContent]:
        """Dispatches calls to 'connect' or core tools."""
        # Robustly strip any server-side prefixes (e.g. 'elemm-gateway-list_offices' -> 'list_offices')
        tool_id = name
        if "-" in tool_id:
            # Check if it starts with the server name or common gateway patterns
            for prefix in [self.server_name, "elemm-gateway", "gateway"]:
                if tool_id.startswith(f"{prefix}-"):
                    tool_id = tool_id[len(prefix)+1:]
                    break
        
        # Also handle colon/dot notation from some clients
        tool_id = tool_id.split(":")[-1].split(".")[-1].strip()

        # Also handle colon/dot notation from some clients
        tool_id = tool_id.split(":")[-1].split(".")[-1].strip().lower()

        # 1. Gateway-Level Tools (Always handled locally)
        if tool_id == "connect_to_site":
            return await self._connect(arguments.get("url", ""))
        
        if tool_id == "execute_sequence":
            actions = arguments.get("actions", [])
            return await self._handle_execute_sequence(actions)

        # 2. Protocol Discovery Tools (Proxied)
        if tool_id in ["get_manifest", "get_landmarks", "inspect_landmark"]:
            if not self.active_site_url:
                return [types.TextContent(type="text", text="Error: Not connected. Call 'connect_to_site' first.")]
            return await self._proxy_core_tool(tool_id, arguments)

        # 3. Dynamic Mirrored Actions (Proxied)
        if not self.active_site_url:
            return [types.TextContent(type="text", text=f"Error: Tool '{tool_id}' requires an active connection. Call 'connect_to_site' first.")]

        res_text = await self._execute_single(tool_id, arguments)
        return [types.TextContent(type="text", text=res_text)]

    async def _handle_execute_sequence(self, actions: List[Dict]) -> List[types.TextContent]:
        """Override to handle 'connect_to_site' inside a sequence."""
        logger.info(f"Gateway: Executing sequence with {len(actions)} actions.")
        if not actions: return []
        
        # Check if first action is connect_to_site (handle prefixes)
        first_action = actions[0]
        aid = first_action.get("action", "").lower()
        if "connect_to_site" in aid:
            url = first_action.get("parameters", {}).get("url", "")
            conn_res = await self._connect(url)
            # If connection failed, return the error immediately
            if "successfully" not in conn_res[0].text:
                return conn_res
            
            # Remove connect action and continue with the rest
            remaining_actions = actions[1:]
            if not remaining_actions:
                return conn_res
            
            results = [f"Step 0 (connect): {conn_res[0].text}"]
            sequence_results = await super()._handle_execute_sequence(remaining_actions)
            results.append(sequence_results[0].text)
            return [types.TextContent(type="text", text="\n\n".join(results))]
            
        return await super()._handle_execute_sequence(actions)

    async def _proxy_core_tool(self, name: str, arguments: dict) -> List[types.TextContent]:
        """Proxies core protocol discovery tools to the remote site."""
        try:
            async with httpx.AsyncClient() as client:
                if name == "get_manifest":
                    # Fetch fresh technical manifest
                    resp = await client.get(f"{self.active_site_url}/.well-known/elemm-manifest.md", params={"technical": "true"})
                    return [types.TextContent(type="text", text=resp.text)]
                
                resp = await client.get(f"{self.active_site_url}/.well-known/elemm-inspect.md", params=arguments)
                return [types.TextContent(type="text", text=resp.text)]
        except Exception as e:
            return [types.TextContent(type="text", text=f"Proxy Error ({name}): {e}")]

    async def _execute_single(self, tool_name: str, arguments: Dict) -> str:
        """UNIVERSAL PROXY: Sends the call to the remote site's execution endpoint."""
        if not self.active_site_url:
            return "Error: Gateway not connected to a remote site."

        try:
            host_key = urlparse(self.active_site_url).netloc
            current_headers = self.session_headers.get(host_key, {})

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.active_site_url}/.well-known/elemm/execute",
                    json={"action_id": tool_name, "parameters": arguments},
                    headers=current_headers,
                    timeout=30.0
                )
                
                if resp.status_code != 200:
                    return f"Remote Error ({resp.status_code}): {resp.text}"
                
                res_data = resp.json()

                # Auto-Capture Auth Tokens
                if isinstance(res_data, dict) and "access_token" in res_data:
                    self.session_headers.setdefault(host_key, {})["Authorization"] = f"Bearer {res_data['access_token']}"
                    logger.info(f"Gateway: Captured token for {host_key}")

                return self._format_result(tool_name, json.dumps(res_data))
        except Exception as e:
            return f"Gateway Connection Error: {str(e)}"

    async def _connect(self, url: str) -> List[types.TextContent]:
        """Fetches the .md manifest and establishes the session."""
        url = url.rstrip("/")
        try:
            async with httpx.AsyncClient() as client:
                manifest_url = f"{url}/.well-known/elemm-manifest.md"
                resp = await client.get(manifest_url, params={"technical": "true"})
                if resp.status_code != 200:
                    return [types.TextContent(type="text", text=f"Failed to find Elemm manifest at {manifest_url}. Status: {resp.status_code}")]

                md_content = resp.text
                
                # Extract AGENT DIRECTIVE
                match = self.SECTION_PATTERN.search(md_content)
                default_directive = (
                    "STRATEGY: Use 'execute_sequence' for ALL multi-step tasks.\n"
                    "PIPING: Use '$alias.field' to pass data between steps.\n"
                    "EFFICIENCY: Do NOT perform one tool call at a time. Batch search and action together."
                )
                directive = match.group(1).strip() if match else default_directive

                # Extract Technical Tools from json-elemm block
                mcp_tools = []
                json_match = self.JSON_BLOCK_PATTERN.search(md_content)
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

    def run(self):
        """Runs the Gateway over STDIO."""
        self.run_stdio()
