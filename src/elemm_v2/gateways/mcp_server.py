import asyncio
import logging
import json
from typing import Any
import mcp.types as types
from mcp.server import Server
from ..core.manager import AIProtocolManager

logger = logging.getLogger("elemm-v2-mcp")

class MCPGateway:
    """MCP-Schnittstelle für elemm_v2."""
    
    def __init__(self, manager: AIProtocolManager, server_name: str = "elemm-v2-server"):
        self.manager = manager
        self.server = Server(server_name)
        self.session_state = {} # Speicher für Cross-Turn Piping
        self.manifest_loaded = False # Safety Lock
        from ..core.sequencer import SequenceEngine
        self.sequencer = SequenceEngine(manager)
        self._setup_server()

    def _setup_server(self):
        @self.server.list_tools()
        async def handle_list_tools() -> list[types.Tool]:
            return [
                types.Tool(
                    name="get_manifest",
                    description="CRITICAL: CALL THIS FIRST. Get the system instructions and command registry.",
                    inputSchema={
                        "type": "object", 
                        "properties": {
                            "full": {"type": "boolean", "description": "If true, returns the complete manifest with all signatures."}
                        }
                    }
                ),

                types.Tool(
                    name="inspect_landmarks",
                    description="Detailed technical discovery. Get tool signatures and schemas for one or more specific landmarks.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "landmark_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "The IDs of the landmarks to inspect."
                            }
                        },
                        "required": ["landmark_ids"]
                    }
                ),
                types.Tool(
                    name="call_action",
                    description="Execute a single action. Use $alias.field for piping.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "action": {"type": "string", "description": "Action ID from manifest."},
                            "parameters": {"type": "object", "description": "Arguments for the action."},
                            "alias": {"type": "string", "description": "Optional alias for result piping."}
                        },
                        "required": ["action"]
                    }
                ),
                types.Tool(
                    name="execute_sequence",
                    description=(
                        "HIGH PERFORMANCE PIPELINE: Execute multiple actions in a single turn. "
                        "Use this for complex tasks requiring data flow between steps. "
                        "PIPING: Use '$alias.field' (e.g. '$step0.id') to pass results. "
                        "IMPORTANT: Directly calling landmark IDs as tools will FAIL. You MUST use this sequence or 'call_action'."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "actions": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "action": {"type": "string", "description": "Landmark ID to execute"},
                                        "alias": {"type": "string", "description": "Unique name for this step's result"},
                                        "parameters": {"type": "object", "description": "Action parameters. Use $alias.field for piping."}
                                    },
                                    "required": ["action"]
                                }
                            }
                        },
                        "required": ["actions"]
                    }
                ),
                types.Tool(
                    name="list_aliases",
                    description="Memory Bank: Show all currently active aliases and their stored values.",
                    inputSchema={"type": "object", "properties": {}}
                )
            ]

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
            arguments = arguments or {}
            
            # 1. Safety Lock & Manifest Loading
            if name == "get_manifest":
                self.manifest_loaded = True
            
            if name in ["call_action", "execute_sequence", "list_aliases"] and not self.manifest_loaded:
                return [types.TextContent(
                    type="text", 
                    text="CRITICAL PROTOCOL VIOLATION: You are operating blindly. You MUST call 'get_manifest' first."
                )]

            if name == "get_manifest":
                is_full = arguments.get("full", False)
                manifest_md = self.manager.get_manifest_md(full=is_full)
                return [types.TextContent(type="text", text=manifest_md)]
            
            if name == "list_aliases":
                aliases = self.manager.list_aliases()
                res = "### GLOBAL ALIAS STORE (Memory Bank)\n"
                if not aliases:
                    res += "- No active aliases."
                else:
                    for a, v in aliases.items():
                        res += f"- **${a}**: {v}\n"
                return [types.TextContent(type="text", text=res)]
            


            if name == "inspect_landmarks":
                lm_ids = arguments.get("landmark_ids", [])
                
                results = []
                for lm_id in lm_ids:
                    landmark = self.manager.landmarks.get(lm_id)
                    if not landmark:
                        results.append(f"Error: Landmark '{lm_id}' not found.")
                        continue
                    
                    res = self.manager.presenter._render_landmark(landmark, global_context=self.manager.global_context)
                    if landmark.tools:
                        res += "\n## Contained Tools:\n"
                        for t in landmark.tools:
                            res += f"- {t.id}: {t.description}\n"
                    results.append(res)
                
                return [types.TextContent(type="text", text="\n\n---\n\n".join(results))]

            if name == "list_aliases":
                aliases = self.manager.list_aliases()
                res = "### 🧠 MEMORY BANK (Current Aliases)\n"
                if not aliases:
                    res += "- No findings stored yet."
                else:
                    for a, v in sorted(aliases.items()):
                        res += f"- **${a}**: {v}\n"
                return [types.TextContent(type="text", text=res)]

            if name == "call_action":
                action_id = arguments.get("action")
                params = arguments.get("parameters", {})
                alias = arguments.get("alias")
                
                res = await self.manager.call_action(action_id, params)
                
                if alias:
                    if alias.startswith("$"):
                        alias = alias[1:]
                    self.manager.global_context[alias] = res
                    
                return [types.TextContent(type="text", text=json.dumps(res, indent=2))]

            if name == "execute_sequence":
                actions = arguments.get("actions", [])
                # Pass global context for persistence
                results = await self.sequencer.run(actions, self.manager.global_context)
                return [types.TextContent(type="text", text=json.dumps(results, indent=2))]

            # 4. Smart Prohibited Call Handler
            landmark = self.manager.landmarks.get(name)
            if landmark:
                if not landmark.handler and landmark.tools:
                    repair = self.manager.repair.handle_namespace_execution_attempt(name)
                else:
                    repair = self.manager.repair.handle_prohibited_direct_call(name, arguments)
                return [types.TextContent(type="text", text=json.dumps(repair.dict(), indent=2))]
            
            return [types.TextContent(type="text", text=f"Tool '{name}' not found.")]

    async def _tool_get_manifest(self, arguments: dict) -> list[types.TextContent]:
        is_full = arguments.get("full", False)
        manifest_md = self.manager.get_manifest_md(full=is_full)
        return [types.TextContent(type="text", text=manifest_md)]

    async def _execute_action(self, action_id: str, params: dict) -> list[types.TextContent]:
        try:
            result = await self.manager.call_action(action_id, params)
            return [types.TextContent(type="text", text=json.dumps(result))]
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error: {str(e)}")]

    def run_stdio(self):
        """Startet den MCP-Server über STDIO."""
        from mcp.server.stdio import stdio_server
        async def main():
            async with stdio_server() as (read, write):
                await self.server.run(read, write, self.server.create_initialization_options())
        
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            pass
