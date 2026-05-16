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
from elemm_gateway.services.openapi_bridge import OpenAPIBridge
from elemm_gateway.services.graphql_bridge import GraphQLBridge
from elemm_gateway.services.manifest_service import ManifestService
from elemm_gateway.services.monitor import get_monitor
from elemm_gateway.services.vault import VaultManager
from elemm_gateway.services.config import ConfigManager
from elemm_gateway.services.security import SecurityPolicy
from elemm_gateway.services.executors import OpenAPIExecutor, GraphQLExecutor
from elemm_gateway.services.hygiene import ResponseSquisher
from elemm_gateway.services.sequencer import SequenceEngine
from elemm_gateway.services.tool_registry import GatewayToolRegistry
from elemm_gateway.services.telemetry import MonitoredReadStream, MonitoredWriteStream

logger = logging.getLogger("elemm-gateway")

class ElemmGateway:
    """
    Elemm Gateway v2: A modular, service-oriented gateway for autonomous tool discovery
    and hygienic execution across Native, OpenAPI, and GraphQL interfaces.
    """
    
    def __init__(self, session_id: str = "default", server_name: str = "elemm-gateway"):
        self.session_id = session_id
        self.server = Server(server_name)
        self.monitor = get_monitor()
        
        # Paths
        config_path = os.path.expanduser("~/.elemm/config.json")
        vault_path = os.path.expanduser("~/.elemm/vault.json")

        # Core Services
        self.config_manager = ConfigManager(config_path)
        self.vault_manager = VaultManager(vault_path)
        self.security_policy = SecurityPolicy(self.config_manager.config)
        self.squisher = ResponseSquisher()
        self.sequence_engine = SequenceEngine(self)
        
        # Executors
        self.openapi_executor = OpenAPIExecutor(self.vault_manager)
        self.graphql_executor = GraphQLExecutor(self.vault_manager)

        # State
        self.connected_sites: Dict[str, Dict[str, Any]] = {}
        self.active_site_url: Optional[str] = None
        self.manifest_loaded = False
        
        # Global Settings
        self.limit_standard = self.config_manager.get("limit_standard", 30000)
        self.limit_inspect = self.config_manager.get("limit_inspect", 20000)
        self.limit_search_items = self.config_manager.get("limit_search_items", 10)
        
        self._setup_handlers()

    def _setup_handlers(self):
        """Bind tools and resources to the MCP server."""
        @self.server.list_tools()
        async def list_tools() -> types.ListToolsResult:
            return types.ListToolsResult(tools=GatewayToolRegistry.get_all_tools())

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> types.CallToolResult:
            res_content = await self._handle_call_tool(name, arguments)
            return types.CallToolResult(content=res_content)

        @self.server.list_resources()
        async def list_resources() -> types.ListResourcesResult:
            return types.ListResourcesResult(resources=[])

        @self.server.list_prompts()
        async def list_prompts() -> types.ListPromptsResult:
            return types.ListPromptsResult(prompts=[])

    async def _handle_call_tool(self, name: str, arguments: dict) -> List[types.TextContent]:
        """Main dispatcher with telemetry and session isolation."""
        try:
            # On-the-fly config reload
            if self.config_manager.reload_if_changed():
                self.security_policy.refresh(self.config_manager.config)
                # Sync other global settings that might have changed
                self.limit_standard = self.config_manager.get("limit_standard", 30000)
                self.limit_inspect = self.config_manager.get("limit_inspect", 20000)
                self.limit_search_items = self.config_manager.get("limit_search_items", 10)

            if arguments is None: arguments = {}
            sid = arguments.get("session_id", self.session_id)
            request_id = str(uuid.uuid4())[:8]
            
            # Determine descriptive action name
            display_name = name
            if name == "call_action":
                display_name = f"call_action({arguments.get('action', 'unknown')})"
            elif name == "execute_sequence":
                steps = arguments.get("actions", []) or arguments.get("steps", [])
                display_name = f"execute_sequence({len(steps)} steps)"

            # Pre-Execution Reporting
            self.monitor.report_activity(
                last_action=f"CALL: {display_name}",
                input_data=arguments,
                status="pending",
                session_id=sid,
                request_id=request_id
            )

            import time
            start_time = time.perf_counter()
            try:
                if name == "execute_sequence":
                    res = await self.sequence_engine.execute(
                        arguments.get("actions", []) or arguments.get("steps", []),
                        session_id=sid,
                        request_id=request_id
                    )
                    status = "success" # execute_sequence handles its own sub-statuses
                elif name in GatewayToolRegistry.CORE_TOOL_NAMES:
                    res = await self._proxy_core_tool(name, arguments, session_id=sid)
                    status = "success"
                else:
                    # Direct call proxy
                    raw_res = await self._execute_single(name, arguments, session_id=sid)
                    res = self._format_result(raw_res)
                    status = "success"
            except Exception as e:
                logger.exception(f"Gateway: Tool '{name}' failed")
                res = [types.TextContent(type="text", text=f"Error: {str(e)}")]
                status = "error"

            duration_ms = int((time.perf_counter() - start_time) * 1000)
            
            # --- GLOBAL KEY FILTER ---
            # Scrub API keys from all responses before sending to agent
            if self.config_manager.get("security", {}).get("prevent_key_leakage", True):
                for item in res:
                    if hasattr(item, 'text') and isinstance(item.text, str):
                        item.text = self._redact_secrets(item.text)
            
            # Post-Execution Reporting
            output_text = res[0].text if (res and hasattr(res[0], 'text')) else str(res)
            self.monitor.report_activity(
                last_action=f"RETURN: {display_name}",
                output_data=output_text,
                status=status,
                session_id=sid,
                request_id=request_id,
                duration_ms=duration_ms,
                manifest=output_text if name == "get_manifest" and status == "success" else None
            )
            
            return res
        except Exception as fatal_err:
            logger.critical(f"FATAL GATEWAY ERROR: {fatal_err}")
            return [types.TextContent(type="text", text=f"Critical Gateway Error: {str(fatal_err)}")]

    def _redact_secrets(self, text: str) -> str:
        """Globally scrubs known API keys from vault to prevent leakage to agents."""
        if not text or not self.vault_manager.vault: return text
        try:
            for host, data in self.vault_manager.vault.items():
                if isinstance(data, str) and len(data) > 6:
                    text = text.replace(data, "[REDACTED_API_KEY]")
                elif isinstance(data, dict):
                    for k, v in data.items():
                        # Redact ANY string in the vault that looks like a secret (length > 6)
                        # We don't filter by key name anymore since 'value' is often used.
                        if isinstance(v, str) and len(v) > 6:
                            text = text.replace(v, f"[REDACTED_API_KEY]")
        except Exception as e:
            logger.error(f"Error during secret redaction: {e}")
        return text

    def _format_result(self, raw_res):
        """Markdown-friendly formatting with semantic squishing."""
        # 1. Safety check for already serialized JSON strings
        if isinstance(raw_res, str) and (raw_res.strip().startswith("{") or raw_res.strip().startswith("[")):
            # It's already JSON (from core or bridge), just return as TextContent
            return [types.TextContent(type="text", text=raw_res)]

        max_str_len = self.limit_standard // 2
        max_list_items = max(20, self.limit_standard // 500)
        
        # 2. Smart Semantic Truncation (Maintains valid JSON)
        squished_res, _ = ResponseSquisher.smart_truncate(
            raw_res,
            max_list_items=max_list_items,
            max_string_length=max_str_len
        )
        
        # 3. Stringify
        res_text = json.dumps(squished_res, indent=2) if not isinstance(squished_res, str) else squished_res
        
        # 4. Final safety cut (only as last resort)
        if len(res_text) > self.limit_standard:
            hint = f"\n\n(Note: Result too large. Truncated to {self.limit_standard} chars.)"
            res_text = res_text[:self.limit_standard - len(hint) - 10] + "..." + hint
            
        return [types.TextContent(type="text", text=res_text)]

    async def _proxy_core_tool(self, name: str, arguments: Dict, session_id: str = "default") -> List[types.TextContent]:
        """Delegates core Elemm tools to specialized services."""
        sid = arguments.get("session_id", session_id)
        
        if name == "clear_session":
            self.sequence_engine.clear_session(sid)
            return [types.TextContent(type="text", text=f"Session memory cleared for: {sid}")]

        if name == "list_aliases":
            return [types.TextContent(type="text", text=self.sequence_engine.format_aliases_markdown(sid))]

        if name == "connect_to_site":
            url = arguments.get("url")
            if not url: return [types.TextContent(type="text", text="Error: URL is required.")]
            return await self._connect(url, session_id=sid)

        url = self.active_site_url
        if not url: return [types.TextContent(type="text", text="Error: Not connected to any site.")]
        site_data = self.connected_sites.get(url)
        
        if not site_data:
            return [types.TextContent(type="text", text="Error: Connection state lost for active site.")]

        if name == "get_manifest":
            self.manifest_loaded = True
            # Build a transient manager to filter the manifest before returning it
            manager = ManifestService._get_transient_manager(site_data)
            if self.security_policy:
                manager.landmarks = {
                    lid: lm for lid, lm in manager.landmarks.items() 
                    if self.security_policy.is_action_allowed(lid)["allowed"]
                }
                manager._rebuild_hierarchy()
            
            # Use the filtered manager to generate the manifest string
            res_text = manager.get_manifest(full=arguments.get("full", False))
            # Inject globals (instructions, etc.)
            res_text = ManifestService.inject_globals(res_text, full=arguments.get("full", False))
            return self._format_result(res_text)
        
        if name == "get_landmarks":
            # For discovery, we also imply manifest is known
            self.manifest_loaded = True
            limit = self.config_manager.get("max_landmarks_per_view", 20)
            return self._format_result(ManifestService.get_landmarks_summary(site_data, security_policy=self.security_policy, limit=limit))

        if name == "call_action":
            action = arguments.get("action")
            params = arguments.get("parameters", {})
            raw_res = await self._execute_single(action, params, session_id=sid)
            return self._format_result(raw_res)

        if name == "inspect_landmark":
            lm_id = arguments.get("landmark_id")
            offset = arguments.get("_offset", 0)
            limit = arguments.get("_limit")
            
            ids = [lm_id] if isinstance(lm_id, str) else lm_id
            # Security Check for each ID
            for tid in ids:
                check = self.security_policy.is_action_allowed(tid)
                if not check["allowed"]:
                    return [types.TextContent(type="text", text=json.dumps({
                        "status": "error",
                        "_PROTOCOL_ERROR": "ACCESS_DENIED",
                        "message": f"Security Policy Violation: Access to '{tid}' is restricted."
                    }, indent=2))]

            res = await ManifestService.inspect_landmark(
                site_url=url, 
                landmark_id=lm_id, 
                vault_manager=self.vault_manager,
                limit=limit or self.limit_inspect, 
                offset=offset, 
                site_data=site_data, 
                site_type=site_data.get("type")
            )
            return self._format_result(res["manifest"] if "manifest" in res else json.dumps(res.get("data", {})))

        if name == "search_landmarks":
            query = arguments.get("query")
            limit = arguments.get("_limit")
            offset = arguments.get("_offset", 0)
            
            res = await ManifestService.search_landmarks(url, site_data, query, limit=limit or self.limit_search_items, offset=offset)
            return self._format_result(res)
            
        return [types.TextContent(type="text", text=f"Error: Core tool '{name}' not supported by gateway.")]

    async def _handle_execute_sequence(self, actions: List[Dict[str, Any]] = None, session_id: str = "default", **kwargs) -> List[types.TextContent]:
        """Compatibility proxy for old test suite."""
        return await self.sequence_engine.execute(actions, session_id, **kwargs)

    async def _execute_openapi(self, tool_name: str, arguments: Dict, session_id: str = "default") -> str:
        return await self._execute_single(tool_name, arguments, session_id)

    async def _execute_graphql(self, tool_name: str, arguments: Dict, session_id: str = "default") -> str:
        return await self._execute_single(tool_name, arguments, session_id)

    async def _execute_single(self, tool_name: str, arguments: Dict, session_id: str = "default") -> str:
        """Universal dispatcher for tool execution (Native/OpenAPI/GraphQL)."""
        site_data = self.connected_sites.get(self.active_site_url) if self.active_site_url else None
        
        # Determine method for security check
        method = None
        if site_data and site_data.get("landmarks"):
            # Landmark objects have .id or .name
            tool_data = next((t for t in site_data["landmarks"] if (
                getattr(t, 'id', None) == tool_name or 
                getattr(t, 'name', None) == tool_name or 
                (isinstance(t, dict) and (t.get('id') == tool_name or t.get('name') == tool_name))
            )), None)
            if tool_data:
                if isinstance(tool_data, dict):
                    method = tool_data.get("meta", {}).get("method")
                else:
                    method = getattr(tool_data, 'meta', {}).get("method")

        check = self.security_policy.is_action_allowed(tool_name, method=method, arguments=arguments)
        if not check["allowed"]:
            res_obj = {
                "status": "error",
                "_PROTOCOL_ERROR": "ACCESS_DENIED",
                "message": check["reason"]
            }
            if "remedy" in check:
                res_obj["remedy"] = check["remedy"]
            return json.dumps(res_obj, indent=2)

        if not self.manifest_loaded and tool_name not in ["connect_to_site", "get_manifest", "clear_session"]:
            return json.dumps({"status": "error", "_PROTOCOL_ERROR": "PROTOCOL_VIOLATION", "message": "Call 'get_manifest' first."}, indent=2)

        if not self.active_site_url and tool_name != "connect_to_site":
            return "Error: Gateway not connected to a remote site."

        # Handle internal tool calls routed via execute_single
        if tool_name in GatewayToolRegistry.CORE_TOOL_NAMES:
            if tool_name == "call_action":
                action = arguments.get("action")
                params = arguments.get("parameters", {})
                return await self._execute_single(action, params, session_id=session_id)
            
            if tool_name == "execute_sequence":
                steps = arguments.get("actions", []) or arguments.get("steps", [])
                res = await self.sequence_engine.execute(steps, session_id=session_id)
                return res[0].text if res else "[]"

            res = await self._proxy_core_tool(tool_name, arguments, session_id=session_id)
            return res[0].text if res else f"Error: Core tool '{tool_name}' returned empty result."

        site_data = self.connected_sites.get(self.active_site_url)
        if site_data and site_data.get("type") in ["openapi", "graphql"]:
            # OpenAPI/GraphQL Execution
            landmarks = site_data.get("landmarks", site_data.get("tools", []))
            tool_data = next((t for t in landmarks if (
                getattr(t, 'id', None) == tool_name or 
                getattr(t, 'name', None) == tool_name or 
                (isinstance(t, dict) and (t.get('id') == tool_name or t.get('name') == tool_name))
            )), None)
            
            if not tool_data:
                # Landmark Namespace Protection
                potential_tools = [getattr(t, 'id', t.get('name', '')) if not isinstance(t, dict) else t.get('name', '') for t in landmarks if (getattr(t, 'id', t.get('name', '')).startswith(f"{tool_name}:") or getattr(t, 'id', t.get('name', '')).startswith(f"{tool_name}_"))]
                if potential_tools:
                    return json.dumps({
                        "status": "error",
                        "_PROTOCOL_ERROR": "STRUCTURAL_ERROR",
                        "message": f"STRUCTURAL ERROR: Landmark Namespace Call Detected. You called '{tool_name}', but that is a functional area (Landmark), not an executable tool.",
                        "remedy": f"Check technical signatures with 'inspect_landmark(landmark_id=\"{tool_name}\")'. Available tools in this area: {potential_tools[:5]}"
                    }, indent=2)
                return f"Error: Tool '{tool_name}' not found."
            
            # Convert Landmark object to dict for executors if needed
            if not isinstance(tool_data, dict):
                # Simple mapping for executor
                tool_dict = {
                    "name": tool_data.id,
                    "meta": tool_data.meta,
                    "parameters": tool_data.parameters
                }
                tool_data = tool_dict

            if site_data["type"] == "graphql":
                return await self.graphql_executor.execute(tool_data, arguments)
            return await self.openapi_executor.execute(tool_data, arguments)

        # Native Elemm Execution
        try:
            select = arguments.pop("_select", None)
            filter_str = arguments.pop("_filter", None)
            limit = arguments.pop("_limit", None)
            offset = arguments.pop("_offset", None)
            
            async with httpx.AsyncClient() as client:
                exec_url = f"{self.active_site_url}/.well-known/elemm/execute"
                resp = await client.post(exec_url, json={"action": tool_name, "parameters": arguments}, timeout=60.0)
                if resp.status_code != 200: return f"Execution Error: {resp.status_code}\n{resp.text}"
                
                data = resp.json()
                data, was_truncated, total = ResponseSquisher.squish(data, select, filter_str, limit, offset)
                
                if was_truncated:
                    res_obj = {
                        "status": "success",
                        "data": data,
                        "_HYGIENE_NOTICE": f"Output truncated for context hygiene. Showing {len(data)} of {total} items.",
                        "remedy": f"The result is large. Use '_offset={offset + len(data) if offset else len(data)}' to fetch the next page of results."
                    }
                    return json.dumps(res_obj, indent=2)

                return json.dumps(data, indent=2)
        except Exception as e:
            return f"Gateway Connection Error: {str(e)}"

    async def _connect(self, url: str, session_id: str = "default") -> List[types.TextContent]:
        """Delegates connection probing to ManifestService."""
        url = url.strip().rstrip("/")
        self.manifest_loaded = False
        
        self.vault_manager.vault = self.vault_manager.load()
        limit = self.config_manager.get("max_tools_per_landmark", 5)
        res = await ManifestService.inspect_url(url, vault_manager=self.vault_manager, limit=limit)
        if res.get("status") == "success":
            self.connected_sites[url] = res
            # Ensure 'landmarks' key exists for consistency
            if "landmarks" not in self.connected_sites[url]:
                self.connected_sites[url]["landmarks"] = res.get("landmarks", res.get("tools", []))
                self.connected_sites[url]["tools"] = res.get("tools", [])
                
            self.active_site_url = url
            display_type = "GraphQL" if res["type"] == "graphql" else res["type"].upper()
            return [types.TextContent(type="text", text=f"SUCCESS: CONNECTED to {display_type} API at {url}\n\nNEXT: Call 'get_manifest'.")]
        
        return [types.TextContent(type="text", text=f"Connection Failed: {res.get('message')}")]

    async def run(self):
        """Runs the MCP server with passive telemetry streams."""
        from mcp.server.stdio import stdio_server
        pending_names = {}

        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="elemm-gateway",
                    server_version="1.2.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )
