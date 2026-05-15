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

import asyncio
import logging
import json
import uuid
from typing import Any
import mcp.types as types
from mcp.server import Server
from ..core.manager import AIProtocolManager
from ..core.mcp import MCPToolFactory

logger = logging.getLogger("elemm-v2-mcp")

try:
    from elemm_gateway.services.monitor import get_monitor
    HAS_MONITOR = True
except ImportError:
    HAS_MONITOR = False
    def get_monitor(): return None

class MCPGateway:
    """MCP-Schnittstelle für elemm_v2."""
    
    def __init__(self, manager: AIProtocolManager, server_name: str = "elemm-v2-server"):
        self.manager = manager
        self.server = Server(server_name)
        self.session_state = {} # Speicher für Cross-Turn Piping
        self.manifest_loaded = False # Safety Lock
        # We use the sequencer already attached to the manager
        self.sequencer = manager.sequencer
        self.monitor = get_monitor()
        self._setup_server()

    def _setup_server(self):
        @self.server.list_tools()
        async def handle_list_tools() -> types.ListToolsResult:
            return types.ListToolsResult(tools=MCPToolFactory.get_core_tools(with_session=False))

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
            arguments = arguments or {}
            
            # Determine descriptive action name (Align with server.py for Dashboard)
            display_name = name
            if name == "call_action":
                display_name = f"call_action({arguments.get('action', 'unknown')})"
            elif name == "execute_sequence":
                steps = arguments.get("actions", []) or arguments.get("steps", [])
                display_name = f"execute_sequence({len(steps)} steps)"

            # Telemetry: Start
            request_id = str(uuid.uuid4())[:8] 
            sid = arguments.get("session_id", "benchmark")
            if HAS_MONITOR and self.monitor:
                self.monitor.report_activity(
                    last_action=f"CALL: {display_name}",
                    input_data=arguments,
                    status="pending",
                    session_id=sid,
                    request_id=request_id
                )

            import time
            start_t = time.perf_counter()
            status = "success"
            
            try:
                res_content = await self._dispatch_tool(name, arguments, request_id, sid)
            except Exception as e:
                logger.exception(f"MCP Gateway error: {e}")
                res_content = [types.TextContent(type="text", text=f"Error: {str(e)}")]
                status = "error"

            duration_ms = int((time.perf_counter() - start_t) * 1000)
            
            # Telemetry: End
            if HAS_MONITOR and self.monitor:
                self.monitor.report_activity(
                    last_action=f"RETURN: {display_name}",
                    output_data=res_content[0].text if res_content and hasattr(res_content[0], 'text') else "",
                    status=status,
                    session_id=sid,
                    request_id=request_id,
                    duration_ms=duration_ms
                )
            
            return res_content

        @self.server.list_resources()
        async def handle_list_resources() -> types.ListResourcesResult:
            return types.ListResourcesResult(resources=[])

    async def _dispatch_tool(self, name: str, arguments: dict, request_id: str, sid: str) -> list[types.TextContent]:
        """Extracted logic for easier monitoring wrapper."""
        # 1. Safety Lock & Manifest Auto-Loading (Soft Lock)
        auto_injected_manifest = None
        if name == "get_manifest":
            self.manifest_loaded = True
        
        if not self.manifest_loaded:
            if name in ["call_action", "execute_sequence", "list_aliases"]:
                return [types.TextContent(
                    type="text", 
                    text="CRITICAL PROTOCOL VIOLATION: You are operating blindly. You MUST call 'get_manifest' first."
                )]
            
            if name in ["search_landmarks", "get_landmarks", "inspect_landmark"]:
                # Soft Lock: Load manifest automatically to save a turn
                logger.info(f"Soft Lock triggered for {name}. Auto-loading manifest.")
                self.manifest_loaded = True
                auto_injected_manifest = self.manager.get_manifest(full=False)

        if name == "get_manifest":
            is_full = arguments.get("full", False)
            manifest_md = self.manager.get_manifest(full=is_full)
            return [types.TextContent(type="text", text=manifest_md)]
        
        if name == "get_landmarks":
            landmarks = self.manager.get_landmarks()
            res = "### AVAILABLE LANDMARKS\n"
            
            limit = 20 # Default for core MCP
            visible = landmarks[:limit]
            remaining = len(landmarks) - limit
            
            for lm in visible:
                res += f"- **{lm.id}**: {lm.description or 'No description.'}\n"
            
            if remaining > 0:
                res += f"\n- (... and {remaining} more landmarks available. Use `get_manifest(landmark_id=\"...\")` with a specific ID to explore other areas.)"
            
            if auto_injected_manifest:
                res = f"NOTICE: Auto-injected protocol manifest (Initial Discovery Attempt).\n\n{auto_injected_manifest}\n\n---\n\n{res}"
                
            return [types.TextContent(type="text", text=res)]

        if name == "list_aliases":
            aliases = self.manager.list_aliases()
            res = "### GLOBAL ALIAS STORE (Memory Bank)\n"
            if not aliases:
                res += "- No active aliases."
            else:
                for a, v in aliases.items():
                    res += f"- **${a}**: {v}\n"
            return [types.TextContent(type="text", text=res)]


        if name == "inspect_landmark":
            lm_id_input = arguments.get("landmark_id")
            if not lm_id_input:
                return [types.TextContent(
                    type="text", 
                    text="PROTOCOL ERROR: 'landmark_id' cannot be empty. Specify which landmarks you want to inspect."
                )]
            
            # Normalize to list
            if isinstance(lm_id_input, str):
                lm_ids = [lm_id_input]
            else:
                lm_ids = lm_id_input

            results = []
            for lm_id in lm_ids:
                results.append(self.manager.inspect_landmark(lm_id))
            
            final_res = "\n\n---\n\n".join(results)
            if auto_injected_manifest:
                final_res = f"NOTICE: Auto-injected protocol manifest (Initial Discovery Attempt).\n\n{auto_injected_manifest}\n\n---\n\n{final_res}"

            return [types.TextContent(type="text", text=final_res)]
        
        if name == "search_landmarks":
            query = arguments.get("query")
            if not query:
                return [types.TextContent(type="text", text="PROTOCOL ERROR: 'query' is required for search.")]
            
            res = self.manager.search_landmarks(query)
            if auto_injected_manifest:
                res = f"NOTICE: Auto-injected protocol manifest (Initial Discovery Attempt).\n\n{auto_injected_manifest}\n\n---\n\n{res}"

            return [types.TextContent(type="text", text=res)]

        if name == "call_action":
            action_id = arguments.get("action")
            raw_params = arguments.get("parameters", {})
            alias = arguments.get("alias")
            
            # Inject alias into params for manager to handle context storage
            if alias:
                if alias.startswith("$"): alias = alias[1:]
                raw_params["_alias"] = alias

            # Resolve piping
            params, err = self.sequencer.resolve_all(raw_params, self.manager.global_context)
            if err:
                return [types.TextContent(
                    type="text", 
                    text=json.dumps({"status": "error", "message": f"Piping failed: {err}"}, indent=2)
                )]
            
            res = await self.manager.call_action(action_id, params)
            return [types.TextContent(type="text", text=json.dumps(res, indent=2))]

        if name == "execute_sequence":
            # Delegate entirely to manager for consistent logic (local stepN, etc.)
            results = await self.manager.execute_sequence(arguments)
            
            if HAS_MONITOR and self.monitor:
                self.monitor.report_activity(
                    last_action="execute_sequence",
                    output_data=json.dumps(results),
                    status="success" if not any("error" in str(r).lower() for r in results) else "error",
                    session_id=sid,
                    request_id=request_id
                )

            return [types.TextContent(type="text", text=json.dumps(results, indent=2))]

        # 4. Smart Prohibited Call Handler
        landmark = self.manager.landmarks.get(name)
        if landmark:
            if not landmark.handler and landmark.tools:
                repair = self.manager.repair.handle_namespace_execution_attempt(name)
            else:
                repair = self.manager.repair.handle_prohibited_direct_call(name, arguments)
            return [types.TextContent(type="text", text=json.dumps(repair.dict(exclude_none=True), indent=2))]
        
        return [types.TextContent(type="text", text=f"Tool '{name}' not found.")]

    async def _tool_get_manifest(self, arguments: dict) -> list[types.TextContent]:
        is_full = arguments.get("full", False)
        manifest_md = self.manager.get_manifest(full=is_full)
        return [types.TextContent(type="text", text=manifest_md)]

    async def _execute_action(self, action_id: str, params: dict) -> list[types.TextContent]:
        result = await self.manager.call_action(action_id, params)
        return [types.TextContent(type="text", text=json.dumps(result))]

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
