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
                    name="get_landmarks",
                    description="High-level discovery. Shows namespaces and available categories (landmarks).",
                    inputSchema={"type": "object", "properties": {}}
                ),
                types.Tool(
                    name="inspect_landmark",
                    description="Detailed technical discovery. Get tool signatures and schemas for a specific landmark.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "landmark_id": {"type": "string", "description": "The ID of the landmark to inspect."}
                        },
                        "required": ["landmark_id"]
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
                )
            ]

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
            arguments = arguments or {}
            
            # 1. Safety Lock & Manifest Loading
            if name in ["get_manifest", "get_landmarks"]:
                self.manifest_loaded = True
            
            if name in ["call_action", "execute_sequence"] and not self.manifest_loaded:
                return [types.TextContent(
                    type="text", 
                    text="CRITICAL PROTOCOL VIOLATION: You are operating blindly. You MUST call 'get_manifest' first to initialize the site-specific command registry and understand the rules before calling execution tools."
                )]

            if name == "get_manifest":
                is_full = arguments.get("full", False)
                manifest_md = self.manager.get_manifest_md(full=is_full)
                return [types.TextContent(type="text", text=manifest_md)]
            
            if name == "get_landmarks":
                landmarks = self.manager.get_landmarks()
                res = "## Available Landmarks\n"
                for lm in landmarks:
                    res += f"- {lm.id}: {lm.description}\n"
                return [types.TextContent(type="text", text=res)]

            if name == "inspect_landmark":
                lm_id = arguments.get("landmark_id")
                landmark = self.manager.landmarks.get(lm_id)
                if not landmark:
                    return [types.TextContent(type="text", text=f"Error: Landmark '{lm_id}' not found.")]
                
                # v2 Enhanced: Nutze den Presenter für konsistente MD-Doku
                res = self.manager.presenter._render_landmark(landmark)
                
                # Falls es ein Namespace ist, zeige auch die Kinder
                if landmark.tools:
                    res += "\n## Contained Tools:\n"
                    for t in landmark.tools:
                        res += f"- {t.id}: {t.description}\n"
                
                return [types.TextContent(type="text", text=res)]

            if name == "call_action":
                action_id = arguments.get("action")
                params = arguments.get("parameters", {})
                
                # Piping-Resolution für Einzelaufrufe
                from ..core.sequencer import PipeResolver
                resolved_params, err = PipeResolver.resolve(params, self.session_state)
                if err: return [types.TextContent(type="text", text=f"Error: {err}")]

                res_content = await self._execute_action(action_id, resolved_params)
                
                # Alias speichern für nächsten Turn (Cross-Turn Persistence)
                alias = arguments.get("alias")
                if alias:
                    try:
                        # Wir versuchen JSON zu parsen, um strukturierte Daten zu speichern
                        data = json.loads(res_content[0].text)
                        self.session_state[alias] = data
                    except:
                        self.session_state[alias] = res_content[0].text
                
                return res_content

            # 3. Execute Sequence
            if name == "execute_sequence":
                actions = arguments.get("actions", [])
                results = await self.sequencer.run(actions, self.session_state)
                
                # Letzten Context in Session State mergen
                for res in results:
                    if "alias" in res:
                        self.session_state[res["alias"]] = res["result"]
                
                return [types.TextContent(type="text", text=json.dumps(results, indent=2))]

            # 4. Fallback: Catch-all for prohibited direct calls or unknown tools
            landmark = self.manager.landmarks.get(name)
            is_landmark = landmark is not None
            
            target_action = name
            if is_landmark and landmark.tools:
                # Suggest the first tool in the landmark area
                target_action = landmark.tools[0].id
            
            msg = f"Direct call to '{name}' prohibited." if is_landmark else f"Action/Tool '{name}' not found."
            
            # Dynamic Copy+Paste Instruction
            remedy = (
                f"You MUST use 'call_action' or 'execute_sequence'.\n"
                f"COPY+PASTE FIX: call_action(action='{target_action}', parameters={json.dumps(arguments)})"
            )
            
            return [types.TextContent(
                type="text", 
                text=f"{msg}\nREMEDY: {remedy}"
            )]

    async def _tool_get_manifest(self, arguments: dict) -> list[types.TextContent]:
        from ..core.presenter import ManifestPresenter
        presenter = ManifestPresenter()
        md_text = presenter.present_manifest(self.manager.get_landmarks())
        return [types.TextContent(type="text", text=md_text)]

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
