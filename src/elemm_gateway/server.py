# Copyright (C) 2026 Marc Stöcker
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import os
import httpx
import logging
import asyncio
import json
import re
from urllib.parse import urlparse
from typing import List, Dict, Any, Optional
from mcp.server import Server
import mcp.types as types
import yaml
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions

from .openapi_bridge import OpenAPIBridge
from .components import VaultManager, OpenAPIExecutor, SequenceEngine, ResponseSquisher

logger = logging.getLogger("elemm-gateway")

class ElemmGateway:
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
        # Modular Components
        self.vault_manager = VaultManager(os.path.expanduser("~/.elemm/vault.json"))
        self.openapi_executor = OpenAPIExecutor(self.vault_manager)
        self.sequence_engine = SequenceEngine(self)

        self.server = Server(server_name)
        self.active_site_url = None
        self.connected_sites = {} # site_url -> {manifest, tools, type, spec}
        self.manifest_loaded = False

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
                description="High-level discovery. Shows namespaces and available categories (landmarks) on the remote site. Use this to understand the system structure.",
                inputSchema={"type": "object", "properties": {}}
            ),
            types.Tool(
                name="get_manifest",
                description="CRITICAL: CALL THIS FIRST. Get the system instructions, protocol rules, and the complete command topology from the remote site.",
                inputSchema={"type": "object", "properties": {}}
            ),
            types.Tool(
                name="inspect_landmark",
                description="Detailed technical discovery. Get tool signatures and schemas for one or more specific landmarks.",
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
                    "NATIVE PIPELINE: Execute a high-performance chain of tools in one turn. MANDATORY for multi-step tasks.\n"
                    "HYGIENE: You MUST use '_select' (fields), '_filter' (key=val), and '_limit' (count) in 'parameters' of each step to prevent context overflow.\n"
                    "PIPING: Use $alias.field (e.g., $res[0].id) to pass data between steps.\n"
                    "EXAMPLE: {actions: [\n"
                    "  {action: 'get_data', alias: 'res', parameters: {id: '123', _select: 'id,name'}},\n"
                    "  {action: 'update_item', parameters: {id: '$res.id'}}\n"
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
            ),
            types.Tool(
                name="call_action",
                description="Execute a single action. NOTE: Use execute_sequence instead for batch operations. Supports hygiene parameters (_select, _filter, _limit) in parameters.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "description": "The Action ID to execute."},
                        "parameters": {"type": "object", "description": "Parameters for the action."}
                    },
                    "required": ["action"]
                }
            )
        ]

        return tools

    async def _handle_call_tool(self, name: str, arguments: dict) -> List[types.TextContent]:
        """Dispatches calls to 'connect' or core tools."""
        # 0. Safety Lock
        if not getattr(self, "manifest_loaded", False) and name not in ["connect_to_site", "get_manifest", "get_landmarks", "execute_sequence"]:
             return [types.TextContent(type="text", text=f"CRITICAL PROTOCOL VIOLATION: You are operating blindly. You MUST call 'get_manifest' first to initialize the site-specific command registry before calling '{name}'.")]

        if name in ["get_manifest", "get_landmarks"]:
            self.manifest_loaded = True

        # Robustly strip any server-side prefixes (e.g. 'elemm-gateway-list_offices' -> 'list_offices')
        tool_id = name
        if "-" in tool_id:
            # Check if it starts with the server name or common gateway patterns
            for prefix in [getattr(self, "server_name", "elemm-gateway"), "elemm-gateway", "gateway"]:
                if tool_id.startswith(f"{prefix}-"):
                    tool_id = tool_id[len(prefix)+1:]
                    break
        
        # Preserve namespaces for v2!
        tool_id = tool_id.strip()

        # 1. Gateway-Level Tools (Always handled locally)
        if tool_id == "connect_to_site":
            return await self._connect(arguments.get("url", ""))
        
        if tool_id == "execute_sequence":
            actions = arguments.get("actions", [])
            return await self._handle_execute_sequence(actions)

        if tool_id == "call_action":
            aid = arguments.get("action", "")
            params = arguments.get("parameters", {})
            return self._format_result(aid, await self._execute_single(aid, params))

        # 2. Protocol Discovery Tools (Proxied)
        if tool_id in ["get_manifest", "get_landmarks", "inspect_landmark"]:
            if not self.active_site_url:
                return [types.TextContent(type="text", text="Error: Not connected. Call 'connect_to_site' first.")]
            return await self._proxy_core_tool(tool_id, arguments)

        # 3. Dynamic Mirrored Actions (Proxied)
        if not self.active_site_url:
            return [types.TextContent(type="text", text=f"Error: Tool '{tool_id}' requires an active connection. Call 'connect_to_site' first.")]

        # Validate against discovered tools to prevent hallucinations
        site_data = self.connected_sites.get(self.active_site_url, {})
        discovered_tools = site_data.get("tools", [])
        valid_ids = [t.get("name") for t in discovered_tools]
        
        if tool_id not in valid_ids:
            msg = f"Error: Tool '{tool_id}' is unknown at '{self.active_site_url}'. Call 'get_manifest' to see the registry of {len(valid_ids)} available tools."
            return [types.TextContent(type="text", text=msg)]

        res_text = await self._execute_single(tool_id, arguments)
        return self._format_result(tool_id, res_text)

    def _format_result(self, tool_id: str, res_text: Any) -> List[types.TextContent]:
        """Unwraps and formats results from remote sites."""
        # Ensure we are working with a string for JSON parsing
        text_val = res_text if isinstance(res_text, str) else json.dumps(res_text)
        
        try:
            res_json = json.loads(text_val)
            # 1. Handle MCP-like list of content
            if isinstance(res_json, list) and len(res_json) > 0 and isinstance(res_json[0], dict) and "type" in res_json[0]:
                return [types.TextContent(**c) for c in res_json]
            
            # 2. Handle structured data (dict/list)
            if isinstance(res_json, (dict, list)):
                return [types.TextContent(type="text", text=json.dumps(res_json, indent=2))]
        except:
            pass

        # 3. Fallback to plain text with efficiency nag
        warning = "\n\n(HINT: Use 'execute_sequence' for better performance and token efficiency!)"
        return [types.TextContent(type="text", text=str(text_val) + warning)]

    async def _handle_execute_sequence(self, actions: List[Dict]) -> List[types.TextContent]:
        """Override to handle 'connect_to_site' inside a sequence and local execution for OpenAPI."""
        logger.info(f"Gateway: Executing sequence with {len(actions)} actions.")
        if not actions: return []
        
        # 1. Extract first action info
        first_action = actions[0]
    async def _handle_execute_sequence(self, actions: List[Dict[str, Any]]) -> List[types.TextContent]:
        """High-performance chain execution with result piping."""
        return await self.sequence_engine.execute(actions)

    async def _proxy_core_tool(self, name: str, arguments: dict) -> List[types.TextContent]:
        """Proxies core protocol discovery tools to the remote site or serves locally for OpenAPI."""
        url = self.active_site_url
        site_data = self.connected_sites.get(url)
        
        # Robust check: try with/without trailing slash
        if not site_data:
            alt_url = url.rstrip("/") if url.endswith("/") else f"{url}/"
            site_data = self.connected_sites.get(alt_url)
        
        if site_data and site_data.get("type") == "openapi":
            logger.info(f"Gateway: Serving '{name}' locally from OpenAPI cache for {url}")
            if name in ["get_manifest", "get_landmarks"]:
                self.manifest_loaded = True
                
            if name == "get_manifest":
                return [types.TextContent(type="text", text=site_data.get("manifest", ""))]
            if name == "get_landmarks":
                tools = site_data.get("tools", [])
                landmarks = {}
                for t in tools:
                    tag = t["name"].split("_", 1)[0] if "_" in t["name"] else "General"
                    if tag not in landmarks: landmarks[tag] = []
                    landmarks[tag].append(t)
                
                summary = "# Discovered API Landmarks\n\n"
                for tag, tag_tools in landmarks.items():
                    summary += f"- **{tag}**: ({len(tag_tools)} tools) Use 'inspect_landmark(\"{tag}\")' to see details.\n"
                return [types.TextContent(type="text", text=summary)]
            if name in ["inspect_landmark", "inspect_landmarks"]:
                lm_id = arguments.get("landmark_id")
                tools = site_data.get("tools", [])
                
                # Render as TypeScript Signatures (Elemm v2 Style)
                output = ["### 🛠️ TECHNICAL SIGNATURES", "```typescript"]
                
                target_ids = [lm_id] if isinstance(lm_id, str) else lm_id
                selected = []
                for t in tools:
                    t_name = t["name"]
                    # Match exact name OR landmark prefix (e.g. 'Weather' matches 'Weather_getCurrentWeather')
                    t_landmark = t_name.split("_", 1)[0] if "_" in t_name else "General"
                    if t_name in target_ids or t_landmark in target_ids:
                        selected.append(t)
                
                if not selected:
                    return [types.TextContent(type="text", text=f"Landmark or Tool '{lm_id}' not found.")]

                for t in selected:
                    # JSDoc
                    output.append("/**")
                    output.append(f" * Tool: {t['name']}")
                    if t.get("description"):
                        output.append(f" * Description: {t['description']}")
                    output.append(" */")
                    
                    # Params
                    schema = t.get("inputSchema", {})
                    props = schema.get("properties", {})
                    req_fields = schema.get("required", [])
                    
                    param_lines = []
                    for p_name, p_details in props.items():
                        ts_type = p_details.get("type", "any")
                        if ts_type == "integer": ts_type = "number"
                        
                        is_req = "" if p_name in req_fields else "?"
                        p_desc = p_details.get("description", "")
                        
                        line = f"    {p_name}{is_req}: {ts_type};"
                        if p_desc:
                            line += f" // {p_desc}"
                        param_lines.append(line)
                    
                    params_str = "{\n" + "\n".join(param_lines) + "\n  }" if param_lines else "{}"
                    output.append(f"function call_action(action: \"{t['name']}\", parameters: {params_str}): any;\n")
                
                output.append("```")
                return [types.TextContent(type="text", text="\n".join(output))]
        
        logger.debug(f"Gateway: Proxying '{name}' to {url} (Local cache miss. Keys: {list(self.connected_sites.keys())})")

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
        """UNIVERSAL PROXY: Sends the call to the remote site's execution endpoint or directly via HTTP for OpenAPI."""
        if not self.active_site_url:
            return "Error: Gateway not connected to a remote site."

        site_data = self.connected_sites.get(self.active_site_url, {})
        if site_data.get("type") == "openapi":
            return await self._execute_openapi(tool_name, arguments)

        try:
            host_key = urlparse(self.active_site_url).netloc
            # Using vault_manager for headers
            headers = self.vault_manager.get_headers(host_key)

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.active_site_url}/.well-known/elemm/execute",
                    json={"action_id": tool_name, "parameters": arguments},
                    headers=headers,
                    timeout=30.0
                )
                
                if resp.status_code != 200:
                    return f"Remote Error ({resp.status_code}): {resp.text}"
                
                res_data = resp.json()

                # Auto-Capture Auth Tokens
                if isinstance(res_data, dict) and "access_token" in res_data:
                    self.vault_manager.set_token(host_key, res_data['access_token'])
                    logger.info(f"Gateway: Captured token for {host_key}")

                return json.dumps(res_data)
        except Exception as e:
            return f"Gateway Connection Error: {str(e)}"

    async def _execute_openapi(self, name: str, arguments: Dict[str, Any]) -> str:
        """Proxies a tool call to the remote OpenAPI endpoint."""
        url = self.active_site_url
        site_data = self.connected_sites.get(url)
        if not site_data:
            return "Error: Site metadata missing."
        
        # Find tool meta
        tool_meta = next((t["meta"] for t in site_data["tools"] if t["name"] == name), None)
        if not tool_meta:
            return f"Error: Tool '{name}' not found in current site."

        return await self.openapi_executor.execute(tool_meta, arguments)

    async def _connect(self, url: str) -> List[types.TextContent]:
        """Fetches the .md manifest and establishes the session."""
        url = url.rstrip("/")
        try:
            async with httpx.AsyncClient() as client:
                # Reload vault on each connect to avoid restarts
                self.vault_manager.vault = self.vault_manager.load()
                
                # 1. Check if it's an OpenAPI JSON/YAML URL
                if any(url.endswith(ext) for ext in [".json", ".yaml", ".yml"]) or "/openapi" in url:
                    resp = await client.get(url, follow_redirects=True)
                    if resp.status_code == 200:
                        try:
                            # Try JSON first, then YAML
                            try:
                                spec = resp.json()
                            except:
                                spec = yaml.safe_load(resp.text)

                            if isinstance(spec, dict) and ("openapi" in spec or "swagger" in spec):
                                logger.info(f"Gateway: Detected OpenAPI spec at {url}")
                                parsed = OpenAPIBridge.parse_spec(spec, url.rsplit("/", 1)[0])
                                md_content = OpenAPIBridge.generate_virtual_manifest(parsed)
                                
                                self.connected_sites[url] = {
                                    "manifest": md_content,
                                    "tools": parsed["tools"],
                                    "type": "openapi",
                                    "spec": spec
                                }
                                self.active_site_url = url
                                
                                # Check for Auth Requirements
                                auth_warning = ""
                                target_url = parsed.get("base_url", "")
                                host_key = urlparse(target_url).netloc if target_url else urlparse(url).netloc
                                
                                schemes = parsed.get("security_schemes", {})
                                if schemes and host_key not in self.vault_manager.vault:
                                    auth_warning = (
                                        "\n\n> [!WARNING]\n"
                                        f"> **AUTHENTICATION REQUIRED**: This site requires {list(schemes.keys())[0]}.\n"
                                        f"> **REMEDY**: Add an entry for '{host_key}' to your `~/.elemm/vault.json`.\n"
                                        "> **INSTRUCTION**: Please inform the user that an API key is required for this service."
                                    )
                                
                                return [types.TextContent(type="text", text=f"Connected to OpenAPI API: {url}\n\nManifest generated dynamically.{auth_warning}")]
                        except Exception as e:
                            logger.exception(f"Gateway: Failed to parse OpenAPI spec from {url}")

                # 2. Standard Elemm Manifest discovery
                manifest_url = f"{url}/.well-known/elemm-manifest.md"
                resp = await client.get(manifest_url, params={"technical": "true"})
                if resp.status_code != 200:
                    return [types.TextContent(type="text", text=f"Failed to find Elemm manifest at {manifest_url}. Status: {resp.status_code}")]

                md_content = resp.text
                
                # Extract AGENT DIRECTIVE
                match = self.SECTION_PATTERN.search(md_content)
                default_directive = (
                    "STRATEGY: Use 'execute_sequence' for ALL multi-step tasks.\n"
                    "HYGIENE: Use '_select', '_filter', and '_limit' in every call to keep context clean.\n"
                    "PIPING: Use '$alias.field' to pass data between steps.\n"
                    "EFFICIENCY: Do NOT perform one tool call at a time. Batch related actions together."
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

    # --- Vault Management ---
    def _load_vault(self):
        return self.vault_manager.load()

    def run_stdio(self):
        """Runs the Gateway over STDIO."""
        # Standard implementation would be here
        pass
 
 
