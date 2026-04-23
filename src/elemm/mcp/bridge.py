import asyncio
import httpx
import logging
import json
import sys
from typing import List, Dict, Any, Callable, Optional
import mcp.types as types
from mcp.server import Server

# Configure logging
logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING) 
logging.getLogger("mcp").setLevel(logging.WARNING)   
logger = logging.getLogger("elemm-bridge")

# Thread-safe session context
from ..core.context import landmark_ctx, session_headers

class LandmarkBridge:
    """
    Hybrid Bridge between ELEMM Protocol and MCP Standard.
    Implements JIT (Just-in-Time) Context Injection for maximum efficiency.
    """
    def __init__(self, manager: Optional[Any] = None, base_url: str = "http://localhost:8001", server_name: str = "elemm-bridge"):
        self.manager = manager
        self.base_url = base_url
        
        # Use agent_welcome as server name if available
        actual_name = manager.agent_welcome if manager and hasattr(manager, "agent_welcome") and manager.agent_welcome else server_name
        self.server_name = actual_name
        self.server = Server(actual_name)
        self.ctx = "root"
        
        self._setup_server()

    def _setup_server(self):
        @self.server.list_tools()
        async def handle_list_tools() -> List[types.Tool]:
            landmark_ctx.set(self.ctx)
            return await self._handle_list_tools()

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict) -> List[types.TextContent]:
            name = self._strip_namespace(name)
            landmark_ctx.set(self.ctx)
            
            # 1. Core Protocol Tools Dispatch
            if name in ["get_manifest", "navigate", "execute_action", "inspect_landmark"]:
                return await self._handle_core_dispatch(name, arguments)
            
            # 2. Native Action Execution
            return await self._execute_native_action(name, arguments)

    def _get_core_tools(self) -> List[types.Tool]:
        """Returns the base protocol tools that are always available."""
        instructions = self.manager.protocol_instructions if self.manager else "Navigate via 'get_manifest' and 'navigate'."
        
        return [
            types.Tool(
                name="get_manifest",
                description=f"ELEMM PROTOCOL: {instructions}. Returns the available landmarks and subsystems.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "landmark_id": {"type": "string", "description": "Optional: Specific landmark to inspect."}
                    }
                },
            ),
            types.Tool(
                name="navigate",
                description="CONTEXT SWITCH: Activate a specific subsystem to access its specialized toolset and local instructions.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "landmark_id": {"type": "string", "description": "The ID of the subsystem to activate (found via get_manifest)."},
                    },
                    "required": ["landmark_id"],
                },
            ),
            types.Tool(
                name="execute_action",
                description="ACTION EXECUTION: Run a specialized protocol tool by providing its action_id and required parameters. Use this for all mission-critical operations.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "action_id": {"type": "string", "description": "The specialized ID of the tool to execute."},
                        "parameters": {"type": "object", "description": "The required input parameters for the tool."},
                    },
                    "required": ["action_id"],
                },
            ),
            types.Tool(
                name="inspect_landmark",
                description="LANDMARK INSPECTION: Retrieve detailed documentation, available tools, and specific instructions for a subsystem without switching context.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "landmark_id": {"type": "string", "description": "The ID of the subsystem to inspect."},
                    },
                    "required": ["landmark_id"],
                },
            ),
            types.Tool(
                name="enter_module",
                description="DEPRECATED: Use 'navigate' instead. Provided for backward compatibility.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "landmark_id": {"type": "string", "description": "The ID of the subsystem to enter."},
                    },
                    "required": ["landmark_id"],
                },
            ),
        ]

    async def _handle_list_tools(self) -> List[types.Tool]:
        """Core logic to generate the list of available tools."""
        # Synchronize local state with ContextVar (Source of Truth)
        current_ctx = landmark_ctx.get()
        self.ctx = current_ctx
        
        # Core Tools are always available
        tools = self._get_core_tools()
        
        if self.manager:
            # We filter actions based on current context
            manifest_data = self.manager.get_manifest(group=current_ctx, agent_view=False)
            actions = manifest_data.get("actions", [])
            from ..core.discovery import convert_actions_to_mcp_tools
            native_tools = convert_actions_to_mcp_tools(actions)
            tools.extend(native_tools)
        
        return tools


    def get_full_mcp_definitions(self) -> List[Dict[str, Any]]:
        """Returns ALL tool definitions in MCP format for technical discovery (e.g. Gateway)."""
        if not self.manager:
            return []
        
        # Use direct access to actions to avoid internal auth checks
        actions = self.manager.actions
        from ..core.discovery import convert_actions_to_mcp_tools
        mcp_tools = convert_actions_to_mcp_tools(actions)
        return [t.model_dump() for t in mcp_tools]

    def _strip_namespace(self, name: str) -> str:
        """Removes client-side prefixes (e.g. 'solaris-hub-get_manifest' -> 'get_manifest')."""
        if "-" not in name:
            return name
        
        potential_action = name.split("-")[-1]
        is_core = potential_action in ["get_manifest", "navigate", "execute_action", "inspect_landmark", "enter_module"]
        is_manager_action = self.manager and hasattr(self.manager, "_registered_ids") and potential_action in self.manager._registered_ids
        
        if is_manager_action or is_core:
            return potential_action
        
        return name

    async def _handle_core_dispatch(self, name: str, arguments: dict) -> List[types.TextContent]:
        if name == "get_manifest":
            return await self._handle_get_manifest(name, arguments)
        
        if name == "navigate":
            res = await self._handle_navigate(name, arguments)
            await self._notify_tool_list_changed()
            return res
            
        if name == "execute_action":
            target_id = arguments.get("action_id", "")
            target_params = arguments.get("parameters", {})
            if not target_id:
                return [types.TextContent(type="text", text="Error: Missing 'action_id' parameter.")]
            
            # Robustness: strip potential server prefixes (e.g. 'solaris-hub-get_nodes' -> 'get_nodes')
            target_id = self._strip_namespace(target_id)
            
            return await self._execute_native_action(target_id, target_params)
            
        if name == "inspect_landmark":
            return await self._handle_inspect_landmark(name, arguments)
            
        if name == "enter_module":
            # Map enter_module to navigate (protocol equivalence)
            return await self._handle_navigate(name, arguments)
            
        return [types.TextContent(type="text", text=f"Error: Unknown core tool '{name}'.")]

    async def _execute_native_action(self, name: str, arguments: dict) -> List[types.TextContent]:
        if not self.manager:
            return [types.TextContent(type="text", text="Error: No protocol manager bound.")]

        action_meta = next((a for a in self.manager.actions if a.id == name), None)
        if not action_meta:
            return [types.TextContent(type="text", text=f"Error: Tool '{name}' not found. Use 'get_manifest' to verify.")]

        # Auto-Pilot / Context Switching
        auto_switched = await self._handle_auto_pilot(action_meta)

        # Inject session headers into context for this task
        from ..core.context import session_headers
        if not hasattr(self, "session_headers"):
            self.session_headers = {}
        token = session_headers.set(self.session_headers)

        try:
            res = await self.manager.call_action(name, arguments)
            
            # Auto-Capture Auth Tokens (Scoped Session Management)
            if isinstance(res, dict) and "access_token" in res:
                from urllib.parse import urlparse
                
                # Determine host for scoping
                parsed = urlparse(action_meta.url)
                host_key = parsed.netloc if parsed.netloc else "elemm-internal"
                
                new_token = res["access_token"]
                all_sessions = session_headers.get().copy()
                
                # Update only the headers for this specific host
                host_headers = all_sessions.get(host_key, {}).copy()
                host_headers["Authorization"] = f"Bearer {new_token}"
                all_sessions[host_key] = host_headers
                
                # Sync back to instance and context
                self.session_headers = all_sessions
                session_headers.set(all_sessions)
                logger.info(f"Session: Auto-captured access_token for host '{host_key}' (Action: {name})")

            output_text = self._format_action_result(name, res, action_meta, auto_switched)
            return [types.TextContent(type="text", text=output_text)]
        except Exception as e:
            return [types.TextContent(type="text", text=self._format_error_feedback(e))]
        finally:
            session_headers.reset(token)

    async def _handle_auto_pilot(self, action_meta) -> bool:
        """Switches context automatically if the tool belongs to a different landmark."""
        current_ctx = landmark_ctx.get()
        tool_groups = action_meta.groups
        is_global = action_meta.global_access
        
        if current_ctx in tool_groups or is_global or not tool_groups:
            return False
            
        new_ctx = tool_groups[0]
        self.ctx = new_ctx
        landmark_ctx.set(new_ctx)
        await self._notify_tool_list_changed()
        return True

    async def _notify_tool_list_changed(self):
        try:
            # We use a safe task creation to avoid blocking the main flow
            asyncio.create_task(self.server.request_context.session.send_tool_list_changed())
        except:
            pass

    def _format_action_result(self, name: str, res: Any, action_meta, auto_switched: bool) -> str:
        # 1. Unpack tuples (e.g. (data, 200) -> data, status)
        status_code = 200
        if isinstance(res, (list, tuple)) and len(res) == 2 and isinstance(res[1], int):
            status_code = res[1]
            res = res[0]

        # Extract dynamic metadata from response
        remedy = None
        instruction = None
        is_error = status_code >= 400 or (isinstance(res, dict) and res.get("status") == "error")

        if isinstance(res, dict):
            remedy = res.get("remedy")
            instruction = res.get("instruction")
            # Clean display data
            res = {k: v for k, v in res.items() if k not in ["remedy", "instruction"]}
        
        # Static Remedy Fallback (Native Python & Uncaught exceptions)
        if is_error and not remedy and action_meta and getattr(action_meta, "remedy", None):
            remedy = action_meta.remedy
        
        # Build Text
        data_text = self._stringify_result(res)
        sections = [f"Res [{name}]: {data_text}"]
        
        # Deduplicate: only add headers if not already in the data_text
        if remedy and remedy not in data_text:
            sections.insert(0, f"REMEDY: {remedy}")
        if instruction and instruction not in data_text:
            sections.insert(0, f"NOTE: {instruction}")
        
        if auto_switched:
            sections.append(f"[Ctx: {self.ctx}] (Switched)")
            
        return "\n".join(sections)

    def _stringify_result(self, res: Any) -> str:
        # 1. Compact success responses
        if isinstance(res, dict) and res.get("status") == "success" and "message" in res:
            return f"OK: {res['message']}"
            
        # 3. Truncate long lists
        if isinstance(res, list):
            if len(res) > 10:
                truncated = res[:10]
                return "\n".join([f"- {json.dumps(item, separators=(',', ':'))}" for item in truncated]) + f"\n... (+{len(res)-10})"
            return "\n".join([f"- {json.dumps(item, separators=(',', ':'))}" for item in res])
            
        # 4. Simplify dicts
        if isinstance(res, dict):
            if not res: return "{}"
            return json.dumps(res, separators=(',', ':'))
            
        return str(res)

    def _format_error_feedback(self, e: Exception) -> str:
        msg = str(e)
        if "detail" in msg:
            try:
                d = json.loads(msg.replace("'", '"')).get("detail", msg)
                msg = d.get("message", d.get("error", str(d))) if isinstance(d, dict) else d
            except: pass
        logger.warning(f"Tool error: {msg}")
        return f"ERR: {msg}. ACTION: Resolve and retry."

    async def _handle_get_manifest(self, _name: str, arguments: dict) -> List[types.TextContent]:
        from .manifest import ManifestGenerator
        landmark_id = arguments.get("landmark_id")
        
        # If a specific landmark is requested, we show its details
        if landmark_id and landmark_id != "root":
            manifest = self.manager.get_manifest(group=landmark_id)
            md = ManifestGenerator.generate_markdown(
                landmarks=[manifest.get("landmark")] if manifest.get("landmark") else [],
                is_root=False
            )
            return [types.TextContent(type="text", text=md)]

        # Default: show root manifest
        md = ManifestGenerator.generate_markdown(
            manager=self.manager,
            system_name=self.manager.agent_welcome if self.manager else "Solaris Hub",
            instructions=self.manager.protocol_instructions if self.manager else "",
            landmarks=self.manager.navigation_landmarks if self.manager else [],
            tools=self.manager.actions if self.manager else [],
            is_root=(self.ctx == "root")
        )
        return [types.TextContent(type="text", text=md)]

    async def _handle_inspect_landmark(self, _name: str, arguments: dict) -> List[types.TextContent]:
        from .manifest import ManifestGenerator
        landmark_id = arguments.get("landmark_id", "")
        if not landmark_id:
            return [types.TextContent(type="text", text="Error: Missing 'landmark_id' parameter.")]
            
        manifest = self.manager.get_manifest(group=landmark_id)
        actions = manifest.get("actions", [])
        
        # Only list IDs and short descriptions to save tokens
        tool_list = "\n".join([f"- {a['id']}: {a.get('description', '')[:100]}" for a in actions])
        return [types.TextContent(type="text", text=f"Landmark '{landmark_id}' Tools:\n{tool_list}")]

    async def _handle_navigate(self, _name: str, arguments: dict) -> List[types.TextContent]:
        landmark_id = arguments.get("landmark_id", "")
        self.ctx = landmark_id
        landmark_ctx.set(landmark_id)
        
        # Get tool names for preview
        manifest = self.manager.get_manifest(group=landmark_id)
        tool_names = [a["id"] for a in manifest.get("actions", [])]
        preview = f" Tools: {', '.join(tool_names)}" if tool_names else ""
        
        await self._notify_tool_list_changed()
        return [types.TextContent(type="text", text=f"Switched to {landmark_id}.{preview}")]

    def run_stdio(self):
        from mcp.server.stdio import stdio_server
        async def _run():
            async with stdio_server() as (read, write):
                await self.server.run(read, write, self.server.create_initialization_options())
        asyncio.run(_run())
