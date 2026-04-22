import asyncio
import httpx
import logging
import json
import sys
from typing import List, Dict, Any, Callable, Optional
from contextvars import ContextVar
import mcp.types as types
from mcp.server import Server

# Configure logging
logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING) 
logging.getLogger("mcp").setLevel(logging.WARNING)   
logger = logging.getLogger("elemm-bridge")

# Thread-safe session context
landmark_ctx: ContextVar[str] = ContextVar("landmark_ctx", default="root")

class LandmarkBridge:
    """
    Hybrid Bridge between ELEMM Protocol and MCP Standard.
    Implements JIT (Just-in-Time) Context Injection for maximum efficiency.
    """
    def __init__(self, manager: Optional[Any] = None, base_url: str = "http://localhost:8001", server_name: str = "elemm-bridge"):
        self.manager = manager
        self.base_url = base_url
        self.server_name = server_name
        self.server = Server(server_name)
        self.ctx = "root"
        
        self._setup_server()

    def _setup_server(self):
        @self.server.list_tools()
        async def handle_list_tools() -> List[types.Tool]:
            landmark_ctx.set(self.ctx)
            current_ctx = landmark_ctx.get()
            
            # Always include core navigation tools
            tools = [
                types.Tool(
                    name="get_manifest",
                    description="SYSTEM DISCOVERY: Call this FIRST to retrieve the full registry of subsystems and the specific Action IDs required to fulfill your mission parameters.",
                    inputSchema={"type": "object", "properties": {}},
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
            ]
            
            # Dynamic Native Tools from current context
            if self.manager:
                mcp_data = self.manager.get_mcp_tools(group=current_ctx)
                for t_dict in mcp_data:
                    tools.append(types.Tool(**t_dict))
            
            return tools

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict) -> List[types.TextContent]:
            name = self._strip_namespace(name)
            landmark_ctx.set(self.ctx)
            
            # 1. Core Protocol Tools Dispatch
            if name in ["get_manifest", "navigate", "execute_action", "inspect_landmark"]:
                return await self._handle_core_dispatch(name, arguments)
            
            # 2. Native Action Execution
            return await self._execute_native_action(name, arguments)

    def _strip_namespace(self, name: str) -> str:
        """Removes client-side prefixes (e.g. 'solaris-hub-get_manifest' -> 'get_manifest')."""
        if "-" not in name:
            return name
        
        potential_action = name.split("-")[-1]
        is_core = potential_action in ["get_manifest", "navigate", "execute_action"]
        is_manager_action = self.manager and any(a.id == potential_action for a in self.manager.actions)
        
        return potential_action if (is_core or is_manager_action) else name

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
            return await self._execute_native_action(target_id, target_params)
            
        if name == "inspect_landmark":
            return await self._handle_inspect_landmark(name, arguments)
            
        return [types.TextContent(type="text", text=f"Error: Unknown core tool '{name}'.")]

    async def _execute_native_action(self, name: str, arguments: dict) -> List[types.TextContent]:
        if not self.manager:
            return [types.TextContent(type="text", text="Error: No protocol manager bound.")]

        action_meta = next((a for a in self.manager.actions if a.id == name), None)
        if not action_meta:
            return [types.TextContent(type="text", text=f"Error: Tool '{name}' not found. Use 'get_manifest' to verify.")]

        # Auto-Pilot / Context Switching
        auto_switched = await self._handle_auto_pilot(action_meta)

        try:
            res = await self.manager.call_action(name, arguments)
            output_text = self._format_action_result(name, res, action_meta, auto_switched)
            return [types.TextContent(type="text", text=output_text)]
        except Exception as e:
            return [types.TextContent(type="text", text=self._format_error_feedback(e))]

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
        # Extract metadata
        remedy = None
        instruction = None
        if isinstance(res, dict):
            remedy = res.get("remedy")
            instruction = res.get("instruction")
            # Clean display data
            res = {k: v for k, v in res.items() if k not in ["remedy", "instruction"]}
        
        # Fallback to manifest metadata
        remedy = remedy or getattr(action_meta, "remedy", None)
        instruction = instruction or getattr(action_meta, "instructions", None)

        # Build Text
        data_text = self._stringify_result(res)
        sections = [f"### ACTION RESULT: {name}", data_text]
        
        if remedy:
            sections.insert(0, f"--- [REMEDY / HINT] ---\n{remedy}\n----------------------\n")
        if instruction:
            sections.insert(0, f"--- [INSTRUCTION] ---\n{instruction}\n---------------------\n")
        
        if auto_switched:
            sections.append(f"\n[PROTOCOL] Automatically switched context to '{self.ctx}'. Toolbelt updated.")
            
        return "\n".join(sections)

    def _stringify_result(self, res: Any) -> str:
        if isinstance(res, list):
            return "\n".join([f"- {json.dumps(item)}" for item in res])
        if isinstance(res, dict):
            return "\n".join([f"{k}: {v}" for k, v in res.items()])
        return str(res)

    def _format_error_feedback(self, e: Exception) -> str:
        error_msg = str(e)
        if "detail" in error_msg:
            try:
                detail = json.loads(error_msg.replace("'", '"')).get("detail", error_msg)
                error_msg = detail.get("message", detail.get("error", str(detail))) if isinstance(detail, dict) else detail
            except:
                pass
        
        logger.warning(f"Tool execution feedback: {error_msg}")
        return f"--- [PROTOCOL REMEDY] ---\n{error_msg}\n\nACTION REQUIRED: Please resolve the issue and RETRY.\n-------------------------"

    async def _handle_get_manifest(self, _name: str, _args: dict) -> List[types.TextContent]:
        from .manifest import ManifestGenerator
        md = ManifestGenerator.generate_markdown(
            system_name=self.manager.agent_welcome if self.manager else "Solaris Hub",
            instructions=self.manager.protocol_instructions if self.manager else "",
            landmarks=self.manager.navigation_landmarks if self.manager else [],
            tools=self.manager.actions if self.manager else []
        )
        return [types.TextContent(type="text", text=md)]

    async def _handle_inspect_landmark(self, _name: str, arguments: dict) -> List[types.TextContent]:
        from .manifest import ManifestGenerator
        landmark_id = arguments.get("landmark_id", "")
        if not landmark_id:
            return [types.TextContent(type="text", text="Error: Missing 'landmark_id' parameter.")]
            
        manifest = self.manager.get_manifest(group=landmark_id)
        actions = manifest.get("actions", [])
        
        md = ManifestGenerator.generate_detailed_landmark(landmark_id, actions)
        return [types.TextContent(type="text", text=md)]

    async def _handle_navigate(self, _name: str, arguments: dict) -> List[types.TextContent]:
        landmark_id = arguments.get("landmark_id", "")
        self.ctx = landmark_id
        landmark_ctx.set(landmark_id)
        
        manifest = self.manager.get_manifest(group=landmark_id)
        actions = manifest.get("actions", [])
        landmark_info = next((l for l in self.manager.navigation_landmarks if l["id"] == landmark_id), {})
        instructions = landmark_info.get("instructions") or landmark_info.get("description", "No specific instructions.")

        tool_list = "\n".join([
            f"- {a['id']}({', '.join([f'{p['name']}: {p['type']}' for p in a.get('parameters', [])])}): {a.get('description', '')}"
            for a in actions
        ]) if actions else "No tools available in this landmark."
        
        msg = f"Context switched to: {landmark_id}.\n\n[LANDMARK INSTRUCTIONS]\n{instructions}\n\nAvailable tools:\n{tool_list}"
        return [types.TextContent(type="text", text=msg)]

    def run_stdio(self):
        from mcp.server.stdio import stdio_server
        async def _run():
            async with stdio_server() as (read, write):
                await self.server.run(read, write, self.server.create_initialization_options())
        asyncio.run(_run())
