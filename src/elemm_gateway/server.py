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
import json
import logging
import asyncio
import re
import uuid
import httpx
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions

import yaml
from elemm_gateway.openapi_bridge import OpenAPIBridge
from elemm_gateway.graphql_bridge import GraphQLBridge
from elemm_gateway.monitor import get_monitor
from elemm_gateway.components import (
    VaultManager, 
    ConfigManager,
    SecurityPolicy,
    OpenAPIExecutor, 
    GraphQLExecutor,
    ResponseSquisher, 
    SequenceEngine
)

logger = logging.getLogger("elemm-gateway")

class ElemmGateway:
    """
    Elemm Gateway v2: A component-based gateway for autonomous tool discovery
    and hygienic execution across Native, OpenAPI, and GraphQL interfaces.
    """
    
    SECTION_PATTERN = re.compile(r"### PROTOCOL RULES\n(.*?)\n###", re.DOTALL)
    JSON_BLOCK_PATTERN = re.compile(r"```json-elemm\n(.*?)\n```", re.DOTALL)

    def __init__(self, server_name: str = "elemm-gateway"):
        # Unique instance ID to differentiate clients in the dashboard
        self.session_id = f"{server_name.lower()}-{uuid.uuid4().hex[:6]}"
        
        # Connected sites storage: {url: {manifest, tools, directive, type}}
        self.connected_sites: Dict[str, Dict[str, Any]] = {}
        self.active_site_url: Optional[str] = None
        self.manifest_loaded = False

        # Modular Components
        self.config_manager = ConfigManager(os.path.expanduser("~/.elemm/config.json"))
        self.security_policy = SecurityPolicy(self.config_manager.config)
        self.vault_manager = VaultManager(os.path.expanduser("~/.elemm/vault.json"))
        self.openapi_executor = OpenAPIExecutor(self.vault_manager)
        self.graphql_executor = GraphQLExecutor(self.vault_manager)
        self.sequence_engine = SequenceEngine(self)
        
        # Configurable Truncation Limits (Anti-Bomb)
        self.limit_standard = self.config_manager.get("limit_standard", 50000)
        self.limit_inspect = self.config_manager.get("limit_inspect", 250000)
        self.monitor = get_monitor()

        self.server = Server(server_name)
        self.session_id = f"{server_name.lower()}-{uuid.uuid4().hex[:6]}"
        self._setup_handlers()
        self.monitor.report_activity(
            active_sites=0, 
            last_action="Gateway Initialized",
            session_id=self.session_id
        )

    def _calculate_total_tokens(self) -> int:
        """Helper to estimate tokens for all connected sites."""
        total = 0
        for site in self.connected_sites.values():
            manifest = site.get("manifest", "")
            total += len(manifest) // 4
        return total

    def _setup_handlers(self):
        @self.server.list_tools()
        async def handle_list_tools() -> List[types.Tool]:
            """Lists core gateway tools and tools from the active remote site."""
            core_tools = [
                types.Tool(
                    name="connect_to_site",
                    description="Connect to an Elemm-compliant website, OpenAPI, or GraphQL API via its URL.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "The URL to connect to (e.g., https://api.example.com/openapi.json)"}
                        },
                        "required": ["url"]
                    }
                ),
                types.Tool(
                    name="get_manifest",
                    description="CRITICAL: Get system instructions and command topology from the active site.",
                    inputSchema={"type": "object", "properties": {}}
                ),
                types.Tool(
                    name="call_action",
                    description="Execute a single action on the remote site. Supports hygiene (_select, _filter, _limit).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "action": {"type": "string", "description": "The Action ID to execute."},
                            "parameters": {"type": "object", "description": "Parameters for the action."}
                        },
                        "required": ["action"]
                    }
                ),
                types.Tool(
                    name="execute_sequence",
                    description="NATIVE PIPELINE: Batch tools in one turn. Every step creates an automatic alias ($step0, $step1...). Access nested data via $alias.path (e.g., $weather.current.temp).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "actions": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "action": {"type": "string"},
                                        "alias": {"type": "string"},
                                        "parameters": {"type": "object"},
                                        "on_error": {"type": "string", "enum": ["stop", "continue"], "default": "stop"}
                                    },
                                    "required": ["action"]
                                }
                            },
                            "steps": {
                                "type": "array",
                                "description": "Alias for 'actions'.",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "action": {"type": "string"},
                                        "alias": {"type": "string"},
                                        "parameters": {"type": "object"},
                                        "on_error": {"type": "string", "enum": ["stop", "continue"], "default": "stop"}
                                    },
                                    "required": ["action"]
                                }
                            },
                            "session_id": {"type": "string", "description": "Optional session ID for memory isolation.", "default": "default"}
                        }
                    }
                ),
                types.Tool(
                    name="clear_session",
                    description="Clears the memory bank for a specific session ID (Privacy).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string", "description": "The session ID to clear.", "default": "default"}
                        }
                    }
                ),
                types.Tool(
                    name="get_landmarks",
                    description="Returns a high-level summary of available landmarks/functional areas on the active site.",
                    inputSchema={"type": "object", "properties": {}}
                ),
                types.Tool(
                    name="inspect_landmark",
                    description="Returns technical TypeScript signatures for one or more landmarks. Use this BEFORE calling an action to see required parameters.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "landmark_id": {
                                "oneOf": [
                                    {"type": "string", "description": "A single landmark ID (e.g. 'repos')"},
                                    {"type": "array", "items": {"type": "string"}, "description": "A list of landmark IDs"}
                                ]
                            }
                        },
                        "required": ["landmark_id"]
                    }
                ),
                types.Tool(
                    name="list_aliases",
                    description="Lists all currently stored findings (aliases) in the memory bank for a session.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string", "description": "The session ID to inspect.", "default": "default"}
                        }
                    }
                )
            ]

            return core_tools

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict | None) -> List[types.TextContent]:
            """Main dispatcher for tool calls."""
            arguments = arguments or {}
            logger.info(f"Gateway: Dispatching tool '{name}'")

            return await self._handle_call_tool(name, arguments)

    async def _handle_execute_sequence(self, actions: List[Dict], session_id: str = "default") -> List[types.TextContent]:
        """Backward compatibility shim for tests."""
        return await self.sequence_engine.execute(actions, session_id=session_id)

    async def _handle_call_tool(self, name: str, arguments: dict) -> List[types.TextContent]:
        """Main dispatcher with centralized monitoring and token tracking."""
        try:
            # 0. Basic safety
            if arguments is None: arguments = {}
            sid = arguments.get("session_id", "default")
            request_id = str(uuid.uuid4())[:8] # Short unique ID for grouping
            
            # 1. Determine descriptive action name
            display_name = name
            if name == "call_action":
                display_name = f"call_action({arguments.get('action', 'unknown')})"
            elif name == "execute_sequence":
                steps = arguments.get("actions", []) or arguments.get("steps", [])
                display_name = f"execute_sequence({len(steps)} steps)"

            # 2. Centralized Reporting (The "Schleuse")
            try:
                self.monitor.report_activity(
                    last_action=f"CALL: {display_name}",
                    input_data=arguments,
                    status="pending",
                    session_id=sid,
                    request_id=request_id
                )
            except Exception as monitor_err:
                logger.warning(f"Gateway: Monitor reporting failed: {monitor_err}")

            # 3. Execute the tool
            import time
            start_time = time.perf_counter()
            try:
                if name == "execute_sequence":
                    res = await self.sequence_engine.execute(
                        arguments.get("actions", []) or arguments.get("steps", []),
                        session_id=sid,
                        request_id=request_id # The Parent ID for all subsequent steps
                    )
                    # For sequences, tokens are already reported per step
                    output_text_for_tokens = str(res)
                elif name == "call_action":
                    action_name = arguments.get("action", "")
                    raw_res = await self._execute_single(action_name, arguments.get("parameters", {}), session_id=sid)
                    output_text_for_tokens = str(raw_res)
                    res = self._format_result(raw_res, name=action_name)
                elif name in ["connect_to_site", "get_manifest", "get_landmarks", "inspect_landmark", "list_aliases", "clear_session"]:
                    tool_res = await self._proxy_core_tool(name, arguments, session_id=sid)
                    output_text_for_tokens = tool_res[0].text if tool_res else ""
                    res = tool_res
                else:
                    raw_res = await self._execute_single(name, arguments, session_id=sid)
                    output_text_for_tokens = str(raw_res)
                    res = self._format_result(raw_res, name=name)
                
                status = "success"
            except Exception as e:
                logger.exception(f"Gateway: Tool '{name}' failed")
                res = [types.TextContent(type="text", text=f"Error: {str(e)}")]
                output_text_for_tokens = str(e)
                status = "error"

            duration_ms = int((time.perf_counter() - start_time) * 1000)
            # TRUE Token Count (on full data)
            actual_tokens_out = len(output_text_for_tokens) // 4

            # 4. Final Reporting
            try:
                output_text = res[0].text if (res and hasattr(res[0], 'text')) else str(res)
                self.monitor.report_activity(
                    last_action=f"RETURN: {display_name}",
                    output_data=output_text,
                    tokens_out=actual_tokens_out, # Send TRUE tokens
                    status=status,
                    session_id=sid,
                    request_id=request_id,
                    duration_ms=duration_ms,
                    full_size=len(output_text_for_tokens)
                )
            except Exception as monitor_err:
                logger.warning(f"Gateway: Final monitor reporting failed: {monitor_err}")
            
            return res
        except Exception as fatal_err:
            # Fatal safety net to prevent process exit
            logger.critical(f"FATAL GATEWAY ERROR: {fatal_err}")
            return [types.TextContent(type="text", text=f"Critical Gateway Error: {str(fatal_err)}")]

    def _format_result(self, text_val: Any, name: str = None) -> List[types.TextContent]:
        res_str = str(text_val)
        # Higher limit for inspection tools as they are critical for agent discovery
        limit = self.limit_inspect if name and "inspect" in name else self.limit_standard
        
        if len(res_str) > limit:
            res_str = res_str[:limit-3] + "...\n\n(Note: Result truncated to prevent context overflow. Use '_select' or '_limit' for better hygiene.)"
        
        warning = "\n\n(HINT: Use 'execute_sequence' for better performance and token efficiency!)"
        return [types.TextContent(type="text", text=res_str + warning)]

    async def _proxy_core_tool(self, name: str, arguments: Dict, session_id: str = "default") -> List[types.TextContent]:
        """Proxies core tools to the remote site or serves them from cache for OpenAPI/GraphQL."""
        sid = arguments.get("session_id", session_id)
        
        # 1. Handle tools that don't need a connection
        if name == "clear_session":
            self.sequence_engine.clear_session(sid)
            return [types.TextContent(type="text", text=f"Session memory cleared for: {sid}")]

        if name == "list_aliases":
            aliases = self.sequence_engine.get_session_aliases(sid)
            res = f"### MEMORY BANK (Session: {sid})\n"
            if not aliases:
                res += "- No findings stored yet in this session."
            else:
                for a, v in sorted(aliases.items()):
                    # Truncate values for privacy and token economy
                    v_str = str(v)
                    if len(v_str) > 200: v_str = v_str[:197] + "..."
                    res += f"- **${a}**: {v_str}\n"
            return [types.TextContent(type="text", text=res)]

        # 2. Tools that DO need a connection (or establish one)
        if name == "connect_to_site":
            url = arguments.get("url")
            if not url:
                return [types.TextContent(type="text", text="Error: URL is required.")]
            
            res = await self._connect(url, session_id=sid)
            self.active_site_url = url
            return res

        url = self.active_site_url
        if not url:
            return [types.TextContent(type="text", text="Error: Not connected to any site.")]

        site_data = self.connected_sites.get(url)
        if not site_data:
            # Try fuzzy match if url has/lacks trailing slash
            alt_url = url.rstrip("/") if url.endswith("/") else f"{url}/"
            site_data = self.connected_sites.get(alt_url)
        
        if site_data:
            logger.info(f"Gateway: Serving '{name}' locally from cache for {url}")
            if name == "get_manifest":
                is_full = arguments.get("full", False)
                # For OpenAPI, the manifest is already stored
                # We apply injection again to ensure correct protocol rules
                self.manifest_loaded = True
                res_text = self._inject_global_landmark(site_data["manifest"], full=is_full)
                return self._format_result(res_text, name=name)
            if name == "get_landmarks":
                if site_data.get("type") == "native":
                    # For native sites, extract topology from the manifest text
                    manifest = site_data.get("manifest", "")
                    landmarks = {}
                    # Simple regex to find "- **`id`**: ..."
                    matches = re.findall(r"- \*\*`(.*?)`\*\*: (.*?)\n", manifest)
                    for lid, desc in matches:
                        if lid == "elemm": continue
                        # Filter by security policy
                        if not self.security_policy.is_action_allowed(f"{lid}_dummy")["allowed"]:
                            continue
                        landmarks[lid] = desc
                    
                    res = "### LANDMARK TOPOLOGY\n"
                    for lid, desc in sorted(landmarks.items()):
                        res += f"- **{lid}**: {desc}\n"
                    return self._format_result(res, name=name)
                
                # Fallback for OpenAPI/GraphQL
                tools = site_data.get("tools", [])
                landmarks = {}
                for t in tools:
                    # Filter by security policy
                    if not self.security_policy.is_action_allowed(t["name"])["allowed"]:
                        continue
                    lm = t["name"].split(":")[0] if ":" in t["name"] else t["name"].split("_", 1)[0]
                    landmarks[lm] = landmarks.get(lm, 0) + 1
                
                res = "### LANDMARK TOPOLOGY\n"
                for lm, count in sorted(landmarks.items()):
                    res += f"- **{lm}**: ({count} tools)\n"
                return self._format_result(res, name=name)

            if name == "inspect_landmark":
                lm_id = arguments.get("landmark_id")
                ids = [lm_id] if isinstance(lm_id, str) else lm_id
                
                # Filter requested IDs by policy
                allowed_ids = []
                for tid in ids:
                    check = self.security_policy.is_action_allowed(f"{tid}_inspect")
                    if check["allowed"]:
                        allowed_ids.append(tid)
                
                if not allowed_ids:
                    return [types.TextContent(type="text", text="Error: Access to the requested landmark(s) is restricted by security policy.")]
                
                ids = allowed_ids # Proceed with only allowed IDs
                
                if site_data.get("type") == "native":
                    # Lazy Load from remote site
                    signatures = []
                    async with httpx.AsyncClient() as client:
                        for tid in ids:
                            inspect_url = f"{self.active_site_url}/.well-known/elemm-manifest.md"
                            resp = await client.get(inspect_url, params={"landmark_id": tid, "technical": "true", "limit": self.limit_inspect}, follow_redirects=True)
                            if resp.status_code == 200:
                                content = resp.text
                                # CLEANUP: Strip technical JSON block from inspection too
                                if "---" in content:
                                    content = content.split("---")[0].strip()
                                signatures.append(content)
                    
                    final_md = "\n\n".join(signatures)
                    return self._format_result(final_md, name=name)

                # Fallback for OpenAPI/GraphQL (already parsed)
                signatures = []
                for tid in ids:
                    # Match exact tool ID or all tools in a landmark namespace
                    relevant_tools = [t for t in site_data["tools"] if t["name"] == tid or t["name"].startswith(f"{tid}:") or t["name"].startswith(f"{tid}_")]
                    
                    for t in relevant_tools:
                        props = t['inputSchema'].get('properties', {})
                        required = t['inputSchema'].get('required', [])
                        
                        sig = f"/**\n * Tool: {t['name']}\n * Description: {t['description']}\n"
                        for p_name, p_schema in props.items():
                            p_type = p_schema.get('type', 'any')
                            p_desc = p_schema.get('description', '')
                            req_mark = "[REQUIRED]" if p_name in required else "[OPTIONAL]"
                            sig += f" * @param {p_name} ({p_type}) {req_mark} {p_desc}\n"
                        sig += " */\n"
                        
                        # Generate TS-style signature
                        params_list = []
                        for p_name, p_schema in props.items():
                            p_type = p_schema.get('type', 'any')
                            opt = "" if p_name in required else "?"
                            params_list.append(f"{p_name}{opt}: {p_type}")
                        
                        sig += f"function call_action(action: '{t['name']}', parameters: {{ {', '.join(params_list)} }}): any;\n"
                        signatures.append(sig)
                
                if not signatures:
                    content = f"No tools found for landmark/id '{ids}'. Use 'elemm:get_landmarks' to see valid names."
                else:
                    content = "### TECHNICAL SIGNATURES\n```typescript\n" + "\n\n".join(signatures) + "\n```"
                    content += "\n\n(HINT: Combine multiple calls into one 'execute_sequence' for maximum token efficiency!)"
                
                return self._format_result(self._inject_global_landmark(content), name=name)
            
            if name == "list_aliases":
                sid = arguments.get("session_id", "default")
                aliases = self.sequence_engine.get_session_aliases(sid)
                res = "### MEMORY BANK (Current Aliases)\n"
                if not aliases:
                    res += "- No findings stored yet."
                else:
                    for a, v in sorted(aliases.items()):
                        res += f"- **${a}**: {v}\n"
                return [types.TextContent(type="text", text=res)]
            
            if name == "execute_sequence":
                return await self.sequence_engine.execute(arguments.get("actions", []))

        return [types.TextContent(type="text", text=f"Error: Core tool '{name}' not supported by gateway.")]

    async def _execute_single(self, tool_name: str, arguments: Dict, session_id: str = "default") -> str:
        """UNIVERSAL PROXY: Sends the call to the remote site's execution endpoint or directly via HTTP for OpenAPI/GraphQL."""
        # 0. Security Policy Enforcement
        check = self.security_policy.is_action_allowed(tool_name)
        if not check["allowed"]:
            logger.warning(f"Gateway: Security Violation - Attempted action '{tool_name}' blocked.")
            return json.dumps({
                "status": "error",
                "_PROTOCOL_ERROR": "ACCESS_DENIED",
                "message": check["reason"],
                "remedy": check["remedy"]
            }, indent=2)

        # 1. Protocol Enforcement (Handshake Check)
        if not self.manifest_loaded and tool_name not in ["connect_to_site", "get_manifest", "clear_session"] and not tool_name.startswith("elemm:"):
            logger.warning(f"Gateway: Protocol Violation - Action '{tool_name}' attempted before 'get_manifest'.")
            return json.dumps({
                "status": "error",
                "_PROTOCOL_ERROR": "PROTOCOL_VIOLATION",
                "message": "Protocol violation: You MUST call 'get_manifest' to receive system instructions before executing any actions.",
                "remedy": "Call 'get_manifest' immediately to authorize the session."
            }, indent=2)

        if not self.active_site_url and tool_name not in ["connect_to_site"] and not tool_name.startswith("elemm:"):
            return "Error: Gateway not connected to a remote site."

        if tool_name == "execute_sequence":
            res = await self.sequence_engine.execute(arguments.get("actions", []), session_id=session_id)
            return res[0].text if res else "No result"

        # Handle Internal Meta Tools (Token Efficiency Optimization)
        if tool_name == "connect_to_site":
            res = await self._connect(arguments.get("url", ""), session_id=session_id)
            return res[0].text if res else "Connected"

        if tool_name.startswith("elemm:"):
            internal_name = tool_name.split(":", 1)[1]
            # Use proxy logic but return stringified result
            res = await self._proxy_core_tool(internal_name, arguments, session_id=session_id)
            return res[0].text if res else "No result"

        site_data = self.connected_sites.get(self.active_site_url)
        if site_data.get("type") in ["openapi", "graphql"]:
            return await self._execute_openapi(tool_name, arguments)

        try:
            async with httpx.AsyncClient() as client:
                # Use v2 execution endpoint
                exec_url = f"{self.active_site_url}/.well-known/elemm/execute"
                payload = {"action": tool_name, "parameters": arguments}
                logger.info(f"Gateway: Executing native call to {exec_url}")
                
                resp = await client.post(exec_url, json=payload, timeout=60.0)
                if resp.status_code != 200:
                    return f"Remote Execution Error: HTTP {resp.status_code}\n{resp.text}"
                return json.dumps(resp.json(), indent=2)
        except Exception as e:
            return f"Gateway Connection Error: {str(e)}"

    async def _execute_openapi(self, name: str, arguments: Dict[str, Any]) -> str:
        """Proxies a tool call to the remote OpenAPI or GraphQL endpoint."""
        from elemm.core.repair import SmartRepairEngine
        
        url = self.active_site_url
        site_data = self.connected_sites.get(url)
        if not site_data:
            return json.dumps({
                "status": "error",
                "message": "Gateway not connected to any site.",
                "remedy": "Use 'connect_to_site' first."
            })
        
        # Find tool meta
        tool_data = next((t for t in site_data["tools"] if t["name"] == name), None)
        if not tool_data:
            # Check if it's a Landmark Namespace (Grouping)
            landmarks = set(t["name"].split("_", 1)[0] for t in site_data["tools"] if "_" in t["name"])
            if name in landmarks:
                repair = SmartRepairEngine.handle_namespace_execution_attempt(name)
                return json.dumps(repair.model_dump(), indent=2)

            # SmartRepair: Find close matches
            available_ids = [t["name"] for t in site_data["tools"]]
            repair = SmartRepairEngine.handle_missing_action(name, available_ids)
            return json.dumps(repair.model_dump(), indent=2)
        
        # Double check policy with method if available
        method = tool_data.get("meta", {}).get("method", "POST")
        check = self.security_policy.is_action_allowed(name, method=method)
        if not check["allowed"]:
            logger.warning(f"Gateway: Security Block - Action '{name}' ({method}) denied.")
            return json.dumps({
                "status": "error",
                "_PROTOCOL_ERROR": "ACCESS_DENIED",
                "message": check["reason"],
                "remedy": check["remedy"]
            }, indent=2)
        
        try:
            if site_data.get("type") == "graphql":
                return await self.graphql_executor.execute(tool_data, arguments)
            else:
                return await self.openapi_executor.execute(tool_data, arguments)
        except Exception as e:
            return json.dumps({
                "status": "error",
                "message": f"Execution failed: {str(e)}",
                "remedy": "Verify technical signatures with 'elemm:inspect_landmark'."
            }, indent=2)

    async def _connect(self, url: str, session_id: str = "default") -> List[types.TextContent]:
        """Fetches the .md manifest and establishes the session."""
        from elemm_gateway.components import ManifestBuilder
        url = url.strip().rstrip("/")
        logger.info(f"Gateway: Connecting to URL: '{url}'")
        # Reset Protocol Handshake
        self.manifest_loaded = False
        try:
            async with httpx.AsyncClient() as client:
                # Reload vault on each connect to avoid restarts
                self.vault_manager.vault = self.vault_manager.load()
                
                # 1. Check for GraphQL (Introspection Probing)
                if "graphql" in url.lower():
                    logger.info(f"Gateway: GraphQL keyword detected in {url}. Probing...")
                    try:
                        resp = await client.post(
                            url,
                            json={"query": GraphQLBridge.INTROSPECTION_QUERY},
                            headers={
                                "Content-Type": "application/json",
                                "User-Agent": "Elemm-Gateway/2.0"
                            },
                            follow_redirects=True,
                            timeout=15.0
                        )
                        if resp.status_code == 200:
                            schema_data = resp.json().get("data")
                            if schema_data:
                                logger.info(f"Gateway: Detected GraphQL API at {url}")
                                parsed = GraphQLBridge.parse_schema(schema_data, url)
                                md_content = OpenAPIBridge.generate_virtual_manifest(parsed)
                                
                                self.connected_sites[url] = {
                                    "manifest": md_content,
                                    "tools": parsed["tools"],
                                    "type": "graphql"
                                }
                                self.active_site_url = url
                                self.monitor.report_activity(
                                    active_sites=len(self.connected_sites),
                                    total_tokens=self._calculate_total_tokens(),
                                    last_action=f"Connected to {url}",
                                    session_id=session_id,
                                    status="success"
                                )
                                return [types.TextContent(type="text", text=f"CONNECTED to GraphQL API: {url}\n\nNEXT REQUIRED STEP: Call 'get_manifest' before any other tool.")]
                            else:
                                return [types.TextContent(type="text", text=f"GraphQL Probing at {url} returned 200 but no 'data'. Body: {resp.text}")]
                        else:
                            return [types.TextContent(type="text", text=f"GraphQL Probing at {url} failed with HTTP {resp.status_code}. Body: {resp.text}")]
                    except Exception as e:
                        logger.warning(f"Gateway: GraphQL probing failed for {url}: {e}")
                        return [types.TextContent(type="text", text=f"GraphQL Probing Error: {str(e)}")]

                # 2. Check if it's an OpenAPI JSON/YAML URL
                if any(url.endswith(ext) for ext in [".json", ".yaml", ".yml"]) or "/openapi" in url:
                    try:
                        resp = await client.get(url, follow_redirects=True, timeout=10.0)
                        if resp.status_code == 200:
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
                                self.monitor.report_activity(
                                    active_sites=len(self.connected_sites),
                                    total_tokens=self._calculate_total_tokens(),
                                    last_action=f"Connected to OpenAPI: {url}",
                                    session_id=session_id,
                                    status="success"
                                )
                                
                                # Check for Auth Requirements
                                auth_warning = ""
                                target_url = parsed.get("base_url", "")
                                host_key = urlparse(target_url).netloc if target_url else urlparse(url).netloc
                                
                                schemes = parsed.get("security_schemes", {})
                                if schemes and host_key not in self.vault_manager.vault:
                                    auth_warning = (
                                        "\n\n[WARNING]\n"
                                        f"AUTHENTICATION REQUIRED: This site requires {list(schemes.keys())[0]}.\n"
                                        f"REMEDY: Add an entry for '{host_key}' to your `~/.elemm/vault.json`.\n"
                                        "INSTRUCTION: Inform the user that an API key is required for this service."
                                    )
                                
                                return [types.TextContent(type="text", text=f"CONNECTED to OpenAPI API: {url}\n\nNEXT REQUIRED STEP: Call 'get_manifest' before any other tool.{auth_warning}")]
                    except Exception as e:
                        logger.warning(f"Gateway: Failed to probe OpenAPI at {url}: {e}")

                # 3. Standard Elemm Manifest discovery (Lazy Loading Pattern)
                manifest_url = f"{url}/.well-known/elemm-manifest.md"
                try:
                    # Only fetch the summary manifest initially (No technical=true here!)
                    resp = await client.get(manifest_url, params={"limit": self.limit_standard}, follow_redirects=True, timeout=10.0)
                    if resp.status_code == 200:
                        md_content = self._inject_global_landmark(resp.text)
                        
                        # Extract AGENT DIRECTIVE
                        match = self.SECTION_PATTERN.search(md_content)
                        directive = match.group(1).strip() if match else ManifestBuilder.PROTOCOL_RULES
                        
                        # In Lazy Loading, we don't parse tools yet. 
                        # We just store the manifest for topology discovery.
                        self.connected_sites[url] = {
                            "manifest": md_content,
                            "tools": [], # Will be filled on-demand or used via proxy
                            "directive": directive,
                            "type": "native"
                        }
                        self.active_site_url = url
                        self.monitor.report_activity(
                            active_sites=len(self.connected_sites),
                            total_tokens=self._calculate_total_tokens(),
                            last_action=f"Connected to Native: {url}",
                            session_id=session_id,
                            status="success"
                        )
                        return [types.TextContent(type="text", text=f"CONNECTED to Elemm site: {url}\n\nNEXT REQUIRED STEP: Call 'get_manifest' before any other tool.")]
                except Exception as e:
                    logger.warning(f"Gateway: Native manifest discovery failed for {url}: {e}")

                return [types.TextContent(type="text", text=f"Failed to find a supported interface at {url}. (Checked GraphQL, OpenAPI, and Native Elemm)")]

        except Exception as e:
            logger.exception("Gateway: Connection fatal error")
            return [types.TextContent(type="text", text=f"Gateway Connection Error: {str(e)}")]

    def _inject_global_landmark(self, manifest: str, full: bool = False) -> str:
        """Injects the virtual 'elemm' landmark and updates discovery hints."""
        from elemm_gateway.components import ManifestBuilder
        return ManifestBuilder.inject_globals(manifest, full=full)

    def _parse_manifest_to_tools(self, md_content: str) -> List[Dict[str, Any]]:
        """Parses technical tools from the json-elemm block in the manifest."""
        mcp_tools = []
        json_match = self.JSON_BLOCK_PATTERN.search(md_content)
        if json_match:
            try:
                mcp_tools = json.loads(json_match.group(1))
                logger.info(f"Gateway: Discovered {len(mcp_tools)} technical tools via json-elemm.")
            except Exception as e:
                logger.warning(f"Gateway: Failed to parse json-elemm block: {e}")
        return mcp_tools

    async def run(self):
        """Runs the MCP server with passive stream monitoring."""
        from mcp.server.stdio import stdio_server
        
        # We store pending request IDs to match response names in the UI
        pending_request_names = {}

        class MonitoredReadStream:
            def __init__(self, stream, monitor, session_id):
                self._stream = stream
                self._monitor = monitor
                self._session_id = session_id

            async def receive(self):
                message = await self._stream.receive()
                try:
                    # Support multiple JSON objects in one stream chunk
                    chunks = message.strip().split("\n")
                    for chunk in chunks:
                        if not chunk.strip(): continue
                        data = json.loads(chunk)
                        method = data.get("method", "unknown")
                        
                        # Extract tool name for tools/call
                        if method == "tools/call":
                            tool_name = data.get("params", {}).get("name")
                        else:
                            tool_name = method

                        msg_id = data.get("id")
                        if msg_id is not None:
                            pending_request_names[msg_id] = tool_name
                        
                        self._monitor.report_activity(
                            last_action=f"WIRE IN: {tool_name}",
                            input_data=data,
                            tokens_in=len(chunk) // 4,
                            status="pending",
                            session_id=self._session_id
                        )
                except:
                    pass
                return message

        class MonitoredWriteStream:
            def __init__(self, stream, monitor, session_id):
                self._stream = stream
                self._monitor = monitor
                self._session_id = session_id

            async def send(self, message):
                try:
                    data = json.loads(message)
                    msg_id = data.get("id")
                    tool_name = pending_request_names.pop(msg_id, "result") if msg_id is not None else "event"
                    
                    self._monitor.report_activity(
                        last_action=f"WIRE OUT: {tool_name}",
                        output_data=data,
                        tokens_out=len(message) // 4,
                        status="success" if "error" not in data else "error",
                        session_id=self._session_id
                    )
                except:
                    pass
                await self._stream.send(message)

        async with stdio_server() as (read_stream, write_stream):
            # Wrap for passive telemetry
            monitored_read = MonitoredReadStream(read_stream, self.monitor, self.session_id)
            monitored_write = MonitoredWriteStream(write_stream, self.monitor, self.session_id)
            
            await self.server.run(
                monitored_read,
                monitored_write,
                InitializationOptions(
                    server_name="elemm-gateway",
                    server_version="1.1.4",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    gateway = ElemmGateway("elemm-gateway")
    asyncio.run(gateway.run())
