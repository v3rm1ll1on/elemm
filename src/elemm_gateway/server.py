# Copyright (C) 2026 Marc Stöcker
# Website: https://elemm.dev
#
# This program is licensed under the Business Source License 1.1 (BSL 1.1).
# See the LICENSE file in the root directory for details.

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
from elemm_gateway.services.executors import OpenAPIExecutor, GraphQLExecutor, MCPExecutor
from elemm_gateway.services.hygiene import ResponseSquisher
from elemm_gateway.services.sequencer import SequenceEngine
from elemm_gateway.services.tool_registry import GatewayToolRegistry
from elemm_gateway.services.telemetry import MonitoredReadStream, MonitoredWriteStream
from elemm_gateway.services.mcp_config import MCPConfigManager
from elemm_gateway.services.mcp_bridge import MCPBridge, MCPProcessManager
from elemm_gateway import __version__

logger = logging.getLogger("elemm-gateway")

class ElemmGateway:
    """
    Elemm Gateway v2: A modular, service-oriented gateway for autonomous tool discovery
    and hygienic execution across Native, OpenAPI, and GraphQL interfaces.
    """
    
    def __init__(self, session_id: str = "default", server_name: str = "elemm-gateway", config_path: Optional[str] = None, vault_path: Optional[str] = None):
        self.session_id = session_id
        self.server = Server(server_name)
        self.monitor = get_monitor()
        
        # Paths
        config_path = config_path or os.path.expanduser("~/.elemm/config.json")
        vault_path = vault_path or os.path.expanduser("~/.elemm/vault.json")

        # Core Services
        self.config_manager = ConfigManager(config_path)
        self.vault_manager = VaultManager(
            vault_path,
            user_agent=self.config_manager.get("user_agent", "ElemmGateway/1.0 (Autonomous Agent)")
        )
        self.security_policy = SecurityPolicy(self.config_manager.config)
        self.squisher = ResponseSquisher()
        self.sequence_engine = SequenceEngine(self)
        
        # MCP Services
        self.mcp_config = MCPConfigManager()
        self.mcp_process_manager = MCPProcessManager()
        self.mcp_bridge = MCPBridge(self.mcp_config, self.mcp_process_manager)
        
        # Executors
        self.openapi_executor = OpenAPIExecutor(self.vault_manager)
        self.graphql_executor = GraphQLExecutor(self.vault_manager)
        self.mcp_executor = MCPExecutor(self.mcp_bridge)

        # State (isolated by connected client session_id)
        self._connected_sites_data: Dict[str, Dict[str, Dict[str, Any]]] = {}  # session_id -> {url -> site_data}
        self.active_site_urls: Dict[str, str] = {}  # session_id -> active_site_url
        self.manifest_loaded = False
        
        # Global Settings
        self.limit_standard = self.config_manager.get("limit_standard", 30000)
        self.limit_inspect = self.config_manager.get("limit_inspect", 20000)
        self.limit_search_items = self.config_manager.get("limit_search_items", 10)
        
        self._setup_handlers()

    def _resolve_session_id(self, session_id: Optional[str] = None, arguments: Optional[Dict] = None) -> str:
        """Resolves the current session ID by checking arguments, manual override, ContextVar, and finally self.session_id."""
        if arguments and isinstance(arguments, dict) and "session_id" in arguments:
            return arguments["session_id"]
        if session_id:
            return session_id
            
        from elemm_gateway.services.connected_clients import current_client_id
        ctx_sid = current_client_id.get()
        if ctx_sid and ctx_sid != "default":
            return ctx_sid
            
        return self.session_id

    @property
    def active_site_url(self) -> Optional[str]:
        """Backwards compatibility for tests accessing global active_site_url directly."""
        return self._get_active_url()

    @active_site_url.setter
    def active_site_url(self, value: str):
        """Backwards compatibility setter for tests."""
        sid = self._resolve_session_id()
        self.active_site_urls[sid] = value

    @property
    def connected_sites(self) -> Dict[str, Dict[str, Any]]:
        """Backwards compatibility for tests accessing global connected_sites directly."""
        return self._get_connected_sites()

    @connected_sites.setter
    def connected_sites(self, value: Dict[str, Dict[str, Any]]):
        """Backwards compatibility setter for tests."""
        sid = self._resolve_session_id()
        self._connected_sites_data[sid] = value

    def _get_active_url(self, session_id: Optional[str] = None) -> Optional[str]:
        sid = self._resolve_session_id(session_id)
        return self.active_site_urls.get(sid)

    def _get_connected_sites(self, session_id: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        sid = self._resolve_session_id(session_id)
        if sid not in self._connected_sites_data:
            self._connected_sites_data[sid] = {}
        return self._connected_sites_data[sid]

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
                self.vault_manager.user_agent = self.config_manager.get("user_agent", "ElemmGateway/1.0 (Autonomous Agent)")

            self.mcp_config.reload_if_changed()

            if arguments is None: arguments = {}
            sid = self._resolve_session_id(arguments=arguments)
            
            # Security Check: Validate the entire tool call against the security policy
            if self.security_policy:
                sec_check = self.security_policy.validate_tool_call(name, arguments)
                if not sec_check["allowed"]:
                    return [types.TextContent(type="text", text=json.dumps({
                        "status": "error",
                        "_PROTOCOL_ERROR": "ACCESS_DENIED",
                        "message": f"Security Policy Violation: {sec_check['reason']}",
                        "remedy": sec_check.get("remedy", "Access to this operation is restricted by security policy.")
                    }, indent=2))]

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
            
            # Post-Execution Reporting (only if not already reported by untruncated sequence layer)
            already_reported = getattr(res[0], "_dashboard_reported", False) if res else False
            if not already_reported:
                # Use raw_res (untruncated) for single executions if available!
                output_to_monitor = raw_res if 'raw_res' in locals() else (res[0].text if (res and hasattr(res[0], 'text')) else str(res))
                self.monitor.report_activity(
                    last_action=f"RETURN: {display_name}",
                    output_data=output_to_monitor,
                    status=status,
                    session_id=sid,
                    request_id=request_id,
                    duration_ms=duration_ms,
                    manifest=output_to_monitor if name == "get_manifest" and status == "success" else None
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

    async def _proxy_core_tool(self, name: str, arguments: Dict, session_id: Optional[str] = None) -> List[types.TextContent]:
        """Delegates core Elemm tools to specialized services."""
        sid = self._resolve_session_id(session_id, arguments)
        
        if name == "clear_session":
            self.sequence_engine.clear_session(sid)
            await self.mcp_process_manager.stop_all()
            return [types.TextContent(type="text", text=f"Session memory and active MCP processes cleared for: {sid}")]

        if name == "list_aliases":
            return [types.TextContent(type="text", text=self.sequence_engine.format_aliases_markdown(sid))]

        if name == "connect_to_site":
            url = arguments.get("url")
            if not url: return [types.TextContent(type="text", text="Error: URL is required.")]
            return await self._connect(url, session_id=sid)

        url = self._get_active_url(sid)
        if not url: return [types.TextContent(type="text", text="Error: Not connected to any site.")]
        site_data = self._get_connected_sites(sid).get(url)
        if site_data:
            await self._inject_mcp_landmarks(site_data)
        
        if not site_data:
            return [types.TextContent(type="text", text="Error: Connection state lost for active site.")]

        if name == "get_manifest":
            self.manifest_loaded = True
            if site_data.get("type") == "native" and not url.lower().startswith("mcp://"):
                try:
                    params = {}
                    if arguments.get("full"):
                        params["full"] = "true"
                    if arguments.get("landmark_id"):
                        params["landmark_id"] = arguments.get("landmark_id")
                    
                    res_text = await ManifestService.fetch_native_manifest(url, params=params, vault_manager=self.vault_manager)
                except Exception as e:
                    res_text = f"Error fetching manifest: {str(e)}"
                
                res_text = ManifestService.inject_globals(res_text, full=arguments.get("full", False))
                return self._format_result(res_text)

            # Build a transient manager to filter the manifest before returning it
            manager = ManifestService._get_transient_manager(site_data)
            if self.security_policy:
                # Filter landmarks based on security policy, including method checks
                manager.landmarks = {
                    lid: lm for lid, lm in manager.landmarks.items() 
                    if self.security_policy.is_action_allowed(
                        lid, 
                        method=lm.meta.get("method") if hasattr(lm, "meta") and isinstance(lm.meta, dict) else (lm.get("meta", {}).get("method") if isinstance(lm, dict) else None)
                    )["allowed"]
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
            if site_data.get("type") == "native" and not url.lower().startswith("mcp://"):
                try:
                    res_text = await ManifestService.fetch_native_manifest(url, vault_manager=self.vault_manager)
                except Exception as e:
                    res_text = f"Error fetching landmarks: {str(e)}"
                
                return self._format_result(res_text)

            limit = self.config_manager.get("max_landmarks_per_view", 20)
            return self._format_result(ManifestService.get_landmarks_summary(site_data, security_policy=self.security_policy, limit=limit))

        if name == "call_action":
            action = arguments.get("action")
            params = arguments.get("parameters", {}).copy()
            for key in ["toolAction", "toolSummary", "waitForPreviousTools", "session_id"]:
                params.pop(key, None)
            raw_res = await self._execute_single(action, params, session_id=sid)
            return self._format_result(raw_res)

        if name == "inspect_landmark":
            lm_id = arguments.get("landmark_id") or arguments.get("landmark")
            if not lm_id:
                return [types.TextContent(type="text", text="Error: 'landmark_id' (or 'landmark') parameter is required for inspect_landmark. Check your spelling (e.g. 'landmark_id' vs 'landmark').")]
            offset = arguments.get("_offset", 0)
            limit = arguments.get("_limit")
            
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
            if not query:
                return [types.TextContent(type="text", text="Error: 'query' parameter is required for search_landmarks.")]
            limit = arguments.get("_limit")
            offset = arguments.get("_offset", 0)
            landmark_id = arguments.get("landmark_id")
            lm_type = arguments.get("type")
            
            # 2. Fetch search results in JSON format
            res_json = await ManifestService.search_landmarks(
                url, site_data, query, 
                limit=limit or self.limit_search_items, 
                offset=offset, 
                output_format="json",
                landmark_id=landmark_id,
                type=lm_type
            )
            
            # 3. Filter JSON search results using the security policy
            if self.security_policy and isinstance(res_json, dict) and "landmarks" in res_json:
                filtered_landmarks = []
                for lm in res_json["landmarks"]:
                    # Support both dict and object
                    lm_id = lm.get("id", lm.get("name")) if isinstance(lm, dict) else getattr(lm, "id", getattr(lm, "name", None))
                    if not lm_id:
                        continue
                    
                    # Check if action is allowed
                    check = self.security_policy.is_action_allowed(lm_id)
                    if not check["allowed"]:
                        continue
                    
                    # Check parameters of the action
                    param_blocked = False
                    params = lm.get("parameters", []) if isinstance(lm, dict) else getattr(lm, "parameters", [])
                    for param in params:
                        param_name = param.get("name", "") if isinstance(param, dict) else getattr(param, "name", "")
                        if self.security_policy.is_pattern_blocked(param_name):
                            param_blocked = True
                            break
                    
                    if param_blocked:
                        continue
                    
                    filtered_landmarks.append(lm)
                res_json["landmarks"] = filtered_landmarks

            # 4. Return result in correct format (markdown or JSON)
            # Default of search_landmarks tool is markdown text
            if isinstance(res_json, dict):
                # Build a transient manager with only the filtered landmarks to format as markdown
                manager = ManifestService._get_transient_manager({"landmarks": res_json.get("landmarks", [])})
                
                # Check for pagination info
                pag = res_json.get("pagination", {})
                res_text = manager.presenter.present_manifest(
                    list(manager.landmarks.values()),
                    instructions=f"# SEARCH RESULTS FOR: {query}",
                    show_technical=True,
                    output_format="markdown",
                    limit=pag.get("limit", limit or self.limit_search_items),
                    offset=pag.get("offset", offset),
                    total=pag.get("total", len(filtered_landmarks)),
                    has_more=pag.get("has_more", False)
                )
                return self._format_result(res_text)
            
            return self._format_result(res_json)
            
        return [types.TextContent(type="text", text=f"Error: Core tool '{name}' not supported by gateway.")]

    async def _handle_execute_sequence(self, actions: List[Dict[str, Any]] = None, session_id: Optional[str] = None, **kwargs) -> List[types.TextContent]:
        """Compatibility proxy for old test suite."""
        sid = self._resolve_session_id(session_id)
        return await self.sequence_engine.execute(actions, sid, **kwargs)

    async def _execute_openapi(self, tool_name: str, arguments: Dict, session_id: Optional[str] = None) -> str:
        return await self._execute_single(tool_name, arguments, session_id)

    async def _execute_graphql(self, tool_name: str, arguments: Dict, session_id: Optional[str] = None) -> str:
        return await self._execute_single(tool_name, arguments, session_id)

    async def _execute_single(self, tool_name: str, arguments: Dict, session_id: Optional[str] = None) -> str:
        """Universal dispatcher for tool execution (Native/OpenAPI/GraphQL)."""
        sid = self._resolve_session_id(session_id)
        if tool_name in ["_elemm-help", "_elemm_help"]:
            help_data = {
                "status": "success",
                "message": "Welcome to the Elemm Onboarding System!",
                "onboarding": {
                    "Quick Examples": {
                        "1. Parallel Independent Actions (Isolating Failures)": {
                            "description": "Failures are isolated per step. Steps are safe to use even if success is uncertain.",
                            "example": {
                                "action": "execute_sequence",
                                "arguments": {
                                    "actions": [
                                        {"action": "city:status_summary", "on_error": "continue"},
                                        {"action": "non_existent_tool_to_demonstrate_isolation", "on_error": "continue"}
                                    ]
                                }
                            }
                        },
                        "2. Sequential Piping (Data Flow)": {
                            "description": "Pipe results from a step into the next using the '$stepN.field' syntax.",
                            "example": {
                                "action": "execute_sequence",
                                "arguments": {
                                    "actions": [
                                        {"action": "city:status_summary", "alias": "summary"},
                                        {"action": "city:get_security_logs", "parameters": {"since_timestamp": "$summary.timestamp"}}
                                    ]
                                }
                            }
                        }
                    },
                    "Discovery & Navigation": {
                        "1. Search Landmarks & Tools": {
                            "description": "Quickly locate specific tools/landmarks using Python REGEX patterns. Use the pipe operator '|' for multiple terms.",
                            "example": {
                                "action": "search_landmarks",
                                "arguments": {
                                    "query": "energy|water",
                                    "_limit": 10
                                }
                            }
                        },
                        "2. Inspect Specific Landmark": {
                            "description": "Fetch technical TypeScript signatures and details for a specific region/district. Paginates using '_offset' if too large.",
                            "example": {
                                "action": "inspect_landmark",
                                "arguments": {
                                    "landmark_id": "suedost",
                                    "_limit": 25,
                                    "_offset": 0
                                }
                            }
                        }
                    },
                    "When to use call_action vs execute_sequence": {
                        "call_action": "Ideal for a single, isolated, exploratory command.",
                        "execute_sequence": "ALWAYS prefer execute_sequence for multiple independent or sequential operations. It batches execution, minimizes agent turns, is extremely performant, and isolates errors dynamically."
                    }
                }
            }
            return json.dumps(help_data, indent=2)

        active_url = self._get_active_url(sid)
        site_data = self._get_connected_sites(sid).get(active_url) if active_url else None
        
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

        check = self.security_policy.validate_tool_call(tool_name, arguments, method=method)
        if not check["allowed"]:
            res_obj = {
                "status": "error",
                "_PROTOCOL_ERROR": "ACCESS_DENIED",
                "message": f"Security Policy Violation: {check['reason']}"
            }
            if "remedy" in check:
                res_obj["remedy"] = check["remedy"]
            return json.dumps(res_obj, indent=2)

        # Route external MCP tools directly
        if tool_name.startswith("mcp:"):
            parts = tool_name.split(":", 2)
            if len(parts) >= 3:
                server_id = parts[1]
                t_name = parts[2]
                
                server_conf = self.mcp_config.get_server(server_id)
                if not server_conf:
                    return json.dumps({
                        "status": "error",
                        "_PROTOCOL_ERROR": "NOT_FOUND",
                        "message": f"MCP Server '{server_id}' is not configured in ~/.elemm/mcp_servers.yaml."
                    }, indent=2)
                
                remedy_msg = None
                remedies = server_conf.get("remedies", {})
                remedy_info = remedies.get(t_name, {})
                if isinstance(remedy_info, dict):
                    remedy_msg = remedy_info.get("on_error")
                elif isinstance(remedy_info, str):
                    remedy_msg = remedy_info

                tool_data = {
                    "name": tool_name,
                    "remedy": remedy_msg,
                    "meta": {
                        "server_id": server_id,
                        "tool_name": t_name
                    }
                }
                return await self.mcp_executor.execute(tool_data, arguments)

        active_url = self._get_active_url(sid)
        if not active_url and tool_name != "connect_to_site":
            return json.dumps({
                "status": "error",
                "_PROTOCOL_ERROR": "DISCONNECTED",
                "message": "Gateway not connected to a remote site.",
                "remedy": "You must connect to an Elemm-compliant website, OpenAPI, or GraphQL API first.",
                "example": "connect_to_site(url='https://api.example.com/openapi.json')"
            }, indent=2)

        if not self.manifest_loaded and tool_name not in ["connect_to_site", "get_manifest", "clear_session"]:
            return json.dumps({
                "status": "error",
                "_PROTOCOL_ERROR": "PROTOCOL_VIOLATION",
                "message": "Call 'get_manifest' first.",
                "remedy": "You must discover the manifest before executing tools. Please call 'get_manifest' or 'get_landmarks' first.",
                "example": "call_action(action='get_manifest')"
            }, indent=2)


        # Handle internal tool calls routed via execute_single
        if tool_name in GatewayToolRegistry.CORE_TOOL_NAMES:
            if tool_name == "call_action":
                action = arguments.get("action")
                params = arguments.get("parameters", {})
                return await self._execute_single(action, params, session_id=sid)
            
            if tool_name == "execute_sequence":
                steps = arguments.get("actions", []) or arguments.get("steps", [])
                res = await self.sequence_engine.execute(steps, session_id=sid)
                return res[0].text if res else "[]"

            res = await self._proxy_core_tool(tool_name, arguments, session_id=sid)
            return res[0].text if res else f"Error: Core tool '{tool_name}' returned empty result."

        active_url = self._get_active_url(sid)
        site_data = self._get_connected_sites(sid).get(active_url)
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
                
                # Fetch fuzzy matches via SmartRepairEngine
                available_ids = [getattr(t, 'id', t.get('name', '')) if not isinstance(t, dict) else t.get('name', '') for t in landmarks]
                from elemm.core.repair import SmartRepairEngine
                repair = SmartRepairEngine.handle_missing_action(tool_name, available_ids)
                return json.dumps({
                    "status": "error",
                    "_PROTOCOL_ERROR": "NOT_FOUND",
                    "message": repair.message,
                    "remedy": repair.remedy
                }, indent=2)
            
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
                active_url = self._get_active_url(sid)
                exec_url = f"{active_url}/.well-known/elemm/execute"
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
            return json.dumps({
                "status": "error",
                "_PROTOCOL_ERROR": "CONNECTION_FAILED",
                "message": f"Gateway Connection Error: {str(e)}",
                "remedy": "Ensure the target API is online and the URL is correct. If the endpoint requires authentication, verify your credentials in ~/.elemm/vault.json."
            }, indent=2)

    async def _connect(self, url: str, session_id: Optional[str] = None) -> List[types.TextContent]:
        """Delegates connection probing to ManifestService."""
        url = url.strip().rstrip("/")
        self.manifest_loaded = False
        
        sid = session_id or self.session_id
        
        # Support pure virtual local MCP environment connection
        if url.lower() in ["mcp://local", "local", "mcp"]:
            connected_sites = self._get_connected_sites(sid)
            connected_sites[url] = {
                "status": "success",
                "type": "native",
                "url": url,
                "landmarks": [],
                "tools": []
            }
            self.active_site_urls[sid] = url
            return [types.TextContent(type="text", text="SUCCESS: CONNECTED to Pure Local MCP Environment.\n\nNEXT: Call 'get_manifest'.")]

        self.vault_manager.vault = self.vault_manager.load()
        limit = self.config_manager.get("max_tools_per_landmark", 5)
        res = await ManifestService.inspect_url(url, vault_manager=self.vault_manager, limit=limit)
        if res.get("status") == "success":
            connected_sites = self._get_connected_sites(sid)
            connected_sites[url] = res
            # Ensure 'landmarks' key exists for consistency
            if "landmarks" not in connected_sites[url]:
                connected_sites[url]["landmarks"] = res.get("landmarks", res.get("tools", []))
                connected_sites[url]["tools"] = res.get("tools", [])
                
            self.active_site_urls[sid] = url
            display_type = "GraphQL" if res["type"] == "graphql" else res["type"].upper()
            return [types.TextContent(type="text", text=f"SUCCESS: CONNECTED to {display_type} API at {url}\n\nNEXT: Call 'get_manifest'.")]
        
        return [types.TextContent(type="text", text=f"Connection Failed: {res.get('message')}")]

    async def _inject_mcp_landmarks(self, site_data: Dict[str, Any]):
        """Injects external MCP server tools as landmarks into the connected site data."""
        if not site_data:
            return
            
        self.mcp_config.reload_if_changed()
        servers = self.mcp_config.get_servers()
        if not servers:
            return

        url = site_data.get("url", "")
        is_local_mcp = url.lower() in ["mcp://local", "local", "mcp"]
        
        mode = self.config_manager.get("mcp_injection_mode", "global")
        allowed_servers = self.config_manager.get("injected_mcp_servers", [])
        allowed_tools = self.config_manager.get("injected_mcp_tools", [])
        
        # If we are not in virtual local mode and mode is 'local', we skip injection completely
        if not is_local_mcp and mode == "local":
            return

        landmarks = site_data.setdefault("landmarks", [])
        
        # Keep track of existing landmark IDs to prevent duplicates
        existing_ids = {
            lm.get("id", lm.get("name")) if isinstance(lm, dict) else getattr(lm, "id", getattr(lm, "name", None))
            for lm in landmarks
        }
        
        from elemm.core.models import Landmark
        for server_id, server_conf in servers.items():
            # Check if this server is allowed under 'selected' mode
            if not is_local_mcp and mode == "selected":
                server_is_allowed = server_id in allowed_servers
                any_tool_allowed = any(
                    t.startswith(f"{server_id}:") or t.startswith(f"mcp:{server_id}:")
                    for t in allowed_tools
                )
                if not server_is_allowed and not any_tool_allowed:
                    continue

            # Discover external tools as action landmarks
            external_landmarks = await self.mcp_bridge.discover_landmarks(server_id)
            
            # Filter tools according to selected mode & security policy
            filtered_tools = []
            for lm in external_landmarks:
                # Security Check: Security policy always overrides first!
                if self.security_policy:
                    sec_check = self.security_policy.is_action_allowed(lm.id)
                    if not sec_check["allowed"]:
                        logger.warning(f"Security Policy: Injection of '{lm.id}' blocked.")
                        continue
                
                # Selection check in selected mode
                if not is_local_mcp and mode == "selected":
                    tool_name = lm.meta.get("tool_name", "") if lm.meta else ""
                    is_server_whitelisted = server_id in allowed_servers
                    is_tool_whitelisted = (
                        lm.id in allowed_tools or
                        f"{server_id}:{tool_name}" in allowed_tools or
                        tool_name in allowed_tools
                    )
                    if not is_server_whitelisted and not is_tool_whitelisted:
                        continue

                filtered_tools.append(lm)

            # If no tools are allowed/available from this server, do not even inject the navigation landmark
            if not filtered_tools:
                continue

            # 1. Add top-level navigation landmark if it doesn't exist and is allowed by Security
            nav_id = f"mcp:{server_id}"
            if self.security_policy:
                nav_check = self.security_policy.is_action_allowed(nav_id)
                if not nav_check["allowed"]:
                    logger.warning(f"Security Policy: Injection of navigation landmark '{nav_id}' blocked.")
                    continue

            if nav_id not in existing_ids:
                landmarks.append(Landmark(
                    id=nav_id,
                    type="navigation",
                    description=server_conf.get("description", f"MCP Server {server_id}"),
                    instructions=server_conf.get("instructions", ""),
                    tools=[],
                    meta={"server_id": server_id}
                ))
                existing_ids.add(nav_id)
            else:
                # Update existing navigation landmark instructions/description
                idx = next((i for i, l in enumerate(landmarks) if (l.get("id") if isinstance(l, dict) else getattr(l, "id", None)) == nav_id), None)
                if idx is not None:
                    if isinstance(landmarks[idx], dict):
                        landmarks[idx]["instructions"] = server_conf.get("instructions", "")
                        landmarks[idx]["description"] = server_conf.get("description", f"MCP Server {server_id}")
                    else:
                        landmarks[idx].instructions = server_conf.get("instructions", "")
                        landmarks[idx].description = server_conf.get("description", f"MCP Server {server_id}")

            # 2. Add filtered action landmarks
            for lm in filtered_tools:
                if lm.id not in existing_ids:
                    landmarks.append(lm)
                    existing_ids.add(lm.id)
                else:
                    # Update existing action landmark remedy, description and parameters on the fly
                    idx = next((i for i, existing_lm in enumerate(landmarks) if (existing_lm.get("id") if isinstance(existing_lm, dict) else getattr(existing_lm, "id", None)) == lm.id), None)
                    if idx is not None:
                        if isinstance(landmarks[idx], dict):
                            landmarks[idx]["remedy"] = lm.remedy
                            landmarks[idx]["description"] = lm.description
                            landmarks[idx]["parameters"] = lm.parameters
                        else:
                            landmarks[idx].remedy = lm.remedy
                            landmarks[idx].description = lm.description
                            landmarks[idx].parameters = lm.parameters

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
                    server_version=__version__,
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )