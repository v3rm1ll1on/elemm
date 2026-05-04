import asyncio
import logging
import json
import re
from typing import List, Dict, Any, Optional, Tuple
import mcp.types as types
from mcp.server import Server
from ..core.context import landmark_ctx, session_headers
from .manifest import ManifestGenerator
from .processor import SequenceProcessor

logger = logging.getLogger("elemm-bridge")

class LandmarkBridge:
    """Elemm Protocol v1.0 Gateway: Discovery, Inspection, and Execution."""
    
    # Pre-compiled regex for result piping: alias[index].field or alias.field
    PIPE_PATTERN = re.compile(r"\$?([a-zA-Z0-9_-]+)(?:\[(\d+)\])?\.([a-zA-Z0-9_-]+)")
    RESULT_WRAP_PATTERN = re.compile(r"(\{.*\}|\[.*\])", re.DOTALL)

    def __init__(self, manager: Optional[Any] = None, base_url: str = "http://localhost:8001", server_name: str = "elemm-bridge", noise_keys: Optional[List[str]] = None):
        self.manager = manager
        self.base_url = base_url
        self.server_name = server_name
        self.server = Server(server_name)
        self.noise_keys = noise_keys or []
        self.manifest = ManifestGenerator(manager, noise_keys=self.noise_keys)
        self.history = [] # Global result history for piping
        self.session_state = {} # Global key-value store for cross-turn piping
        self.manifest_loaded = False # Safety lock to prevent blind execution
        
        # Internal processing logic
        self.processor = SequenceProcessor(
            manager=manager,
            manifest=self.manifest,
            session_state=self.session_state,
            pipe_pattern=self.PIPE_PATTERN,
            wrap_pattern=self.RESULT_WRAP_PATTERN,
            noise_keys=self.noise_keys
        )
        
        self._setup_server()

    def _setup_server(self):
        @self.server.list_tools()
        async def handle_list_tools() -> List[types.Tool]:
            return [
                types.Tool(
                    name="get_manifest",
                    description="CRITICAL: CALL THIS FIRST. Get the system instructions, protocol rules, and the complete command topology.",
                    inputSchema={"type": "object", "properties": {}}
                ),
                types.Tool(
                    name="execute_sequence",
                    description=(
                        "NATIVE PIPELINE: Execute a high-performance chain of tools in one turn. MANDATORY for multi-step tasks.\n"
                        "PIPING: Use $alias.field (e.g., $res[0].id) to pass data between steps.\n"
                        "Do NOT include MCP tools (get_manifest, etc.) inside a sequence."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "actions": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "action": {"type": "string", "description": "Tool ID from manifest."},
                                        "alias": {"type": "string", "description": "Optional piping alias."},
                                        "parameters": {"type": "object", "description": "Arguments."}
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
                    description="Execute a single action. NOTE: Use execute_sequence instead for batch operations.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "action": {"type": "string", "description": "Action ID."},
                            "alias": {"type": "string", "description": "Optional piping alias."},
                            "parameters": {"type": "object", "description": "Arguments."}
                        },
                        "required": ["action"]
                    }
                ),
                types.Tool(
                    name="inspect_landmark",
                    description="Detailed technical discovery. Get tool signatures and schemas for specific landmarks.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "landmark_id": {"oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]}
                        },
                        "required": ["landmark_id"]
                    }
                ),
                types.Tool(
                    name="get_landmarks",
                    description="High-level discovery. Shows namespaces and available categories (landmarks) on this site.",
                    inputSchema={"type": "object", "properties": {}}
                )
            ]

        # Dispatcher map for tool calls
        self.handlers = {
            "get_landmarks": self._tool_get_landmarks,
            "get_manifest": self._tool_get_manifest,
            "inspect_landmark": self._tool_inspect_landmark,
            "call_action": self._tool_call_action,
            "execute_sequence": self._tool_execute_sequence
        }

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict) -> List[types.TextContent]:
            try:
                # 1. Update manifest status
                if name in ["get_manifest", "get_landmarks"]:
                    self.manifest_loaded = True

                # 2. Safety Lock: Prevent blind execution
                if name in ["call_action", "execute_sequence"] and not self.manifest_loaded:
                    return [types.TextContent(
                        type="text", 
                        text=f"CRITICAL PROTOCOL VIOLATION: You are operating blindly. You MUST call 'get_manifest' first to initialize the site-specific command registry and understand the rules before calling '{name}'."
                    )]

                # 3. Handle prohibited direct calls
                if name not in self.handlers:
                    import json
                    args_str = json.dumps(arguments or {})
                    example = f'{{"action": "{name}", "parameters": {args_str}}}'
                    
                    return [types.TextContent(
                        type="text", 
                        text=f"Direct call to '{name}' prohibited. Use 'execute_sequence' or 'call_action'.\n"
                             f"Example: call_action(action='{name}', parameters={args_str})"
                    )]

                # 4. Dispatch to handler
                return await self.handlers[name](arguments)

            except Exception as e:
                logger.exception(f"Tool execution failed: {e}")
                error_msg = f"Critical Error: {str(e)}"
                if "not found" in str(e).lower():
                    error_msg += ". Ensure you are using the correct tool name from the manifest."
                return [types.TextContent(type="text", text=error_msg)]

    async def _tool_get_landmarks(self, arguments: dict) -> List[types.TextContent]:
        warning = "\n\nNOTE: This is a summary. Call 'get_manifest' for parameter schemas."
        return [types.TextContent(type="text", text=self.manifest.generate_summary() + warning)]

    async def _tool_get_manifest(self, arguments: dict) -> List[types.TextContent]:
        return [types.TextContent(type="text", text=self.manifest.generate_full())]

    async def _tool_inspect_landmark(self, arguments: dict) -> List[types.TextContent]:
        lid = arguments.get("landmark_id") or arguments.get("landmark_ids")
        return [types.TextContent(type="text", text=self.manifest.generate_landmark_detail(lid))]

    async def _tool_call_action(self, arguments: dict) -> List[types.TextContent]:
        aid = arguments.get("action", "")
        params = arguments.get("parameters", {})
        alias = arguments.get("alias")
        
        resolved_params, pipe_error = self.processor.resolve_params(params, {})
        if pipe_error:
            return [types.TextContent(type="text", text=f"FAILED. {pipe_error}")]
            
        res_text = await self.processor.execute_single(aid, resolved_params)
        if alias:
            self.session_state[alias] = self.processor._parse_result(res_text)
            
        formatted = self.processor.format_result(aid, res_text)
        return [types.TextContent(type="text", text=formatted)]

    async def _tool_execute_sequence(self, arguments: dict) -> List[types.TextContent]:
        actions = arguments.get("actions", [])
        return await self.processor.handle_execute_sequence(actions)

    def run_stdio(self):
        """Runs the MCP server over STDIO."""
        from mcp.server.stdio import stdio_server
        async def main():
            async with stdio_server() as (read, write):
                await self.server.run(read, write, self.server.create_initialization_options())
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            pass
