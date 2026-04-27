import asyncio
import logging
import json
import re
from typing import List, Dict, Any, Optional, Tuple
import mcp.types as types
from mcp.server import Server
from ..core.context import landmark_ctx, session_headers
from .manifest import ManifestGenerator

logger = logging.getLogger("elemm-bridge")

class LandmarkBridge:
    """Elemm Protocol v1.0 Gateway: Discovery, Inspection, and Execution."""
    
    def __init__(self, manager: Optional[Any] = None, base_url: str = "http://localhost:8001", server_name: str = "elemm-bridge"):
        self.manager = manager
        self.base_url = base_url
        self.server_name = server_name
        self.server = Server(server_name)
        self.manifest = ManifestGenerator(manager)
        self.history = [] # Global result history for piping
        
        self._setup_server()

    def _setup_server(self):
        @self.server.list_tools()
        async def handle_list_tools() -> List[types.Tool]:
            return [
                types.Tool(
                    name="get_landmarks",
                    description="Get the map of namespaces (landmarks) and their objectives.",
                    inputSchema={"type": "object", "properties": {}}
                ),
                types.Tool(
                    name="get_manifest",
                    description="Get the FULL manifest with ALL tool signatures across ALL landmarks in one call.",
                    inputSchema={"type": "object", "properties": {}}
                ),
                types.Tool(
                    name="inspect_landmark",
                    description="Get detailed tool signatures for a specific landmark.",
                    inputSchema={
                        "type": "object", 
                        "properties": {"landmark_id": {"type": "string"}},
                        "required": ["landmark_id"]
                    }
                ),
                types.Tool(
                    name="execute_sequence",
                    description="Execute a chain of tools. Use $alias.field or $0.field to pipe results.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "actions": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "action": {"type": "string", "description": "The ID of the tool to execute."},
                                        "alias": {"type": "string", "description": "Optional name for result piping (e.g. 'logs')."},
                                        "parameters": {"type": "object", "description": "Arguments for the tool."}
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
        async def handle_call_tool(name: str, arguments: dict) -> List[types.TextContent]:
            try:
                name = name.split(":")[-1].split(".")[-1].strip()
                
                if name == "get_landmarks":
                    return [types.TextContent(type="text", text=self.manifest.generate_summary())]
                if name == "get_manifest":
                    return [types.TextContent(type="text", text=self.manifest.generate_full())]
                if name == "inspect_landmark":
                    lid = arguments.get("landmark_id") or arguments.get("landmark_ids")
                    return [types.TextContent(type="text", text=self.manifest.generate_landmark_detail(lid))]
                if name == "execute_sequence":
                    actions = arguments.get("actions", [])
                    return await self._handle_execute_sequence(actions)
                
                res_text = await self._execute_single(name, arguments)
                return [types.TextContent(type="text", text=res_text)]
            except Exception as e:
                logger.exception(f"Tool execution failed: {e}")
                return [types.TextContent(type="text", text=f"Critical Error: {str(e)}")]

    async def _handle_execute_sequence(self, actions: List[Dict]) -> List[types.TextContent]:
        results = []
        local_results = {} # Maps index (str) OR alias to result
        failed_steps = set()
        
        for i, act in enumerate(actions):
            raw_aid = act.get("action", "") or act.get("action_id", "")
            params = act.get("parameters", {})
            alias = act.get("alias")
            
            aid = raw_aid.strip()
            if ":" in aid: aid = aid.split(":")[-1].strip()
            if "." in aid: aid = aid.split(".")[-1].strip()
            
            if self._depends_on_failed(params, failed_steps, local_results):
                results.append(f"Step {i} ({aid}): SKIPPED")
                failed_steps.add(str(i))
                if alias: failed_steps.add(alias)
                continue
            
            if aid in ["inspect_landmark", "get_landmarks"]:
                res_text = self.manifest.generate_summary() if aid == "get_landmarks" else self.manifest.generate_landmark_detail(params.get("landmark_id"))
                res_obj = self._parse_result(res_text)
            else:
                resolved_params, pipe_error = self._resolve_params(params, local_results)
                if pipe_error:
                    results.append(f"Step {i} ({aid}): FAILED. {pipe_error}")
                    failed_steps.add(str(i))
                    if alias: failed_steps.add(alias)
                    continue
                
                res_text = await self._execute_single(aid, resolved_params)
                res_obj = self._parse_result(res_text)
            
            local_results[str(i)] = res_obj
            if alias: local_results[alias] = res_obj
            self.history.append(res_obj)
            
            if isinstance(res_obj, dict) and res_obj.get("status") == "error":
                failed_steps.add(str(i))
                if alias: failed_steps.add(alias)
            
            formatted_res = self._format_result(aid, res_text)
            results.append(f"Step {i}{' (' + alias + ')' if alias else ''} ({aid}): {formatted_res}")
            
        return [types.TextContent(type="text", text="\n\n".join(results))]

    def _depends_on_failed(self, params: Dict, failed_steps: set, local_results: Dict) -> bool:
        if not params or not failed_steps: return False
        param_str = json.dumps(params)
        placeholders = re.findall(r"\$([a-zA-Z0-9_-]+)(?:\[(\d+)\])?\.([a-zA-Z0-9_-]+)", param_str)
        for step_key, _, _ in placeholders:
            if step_key in failed_steps: return True
        return False

    def _format_result(self, tool_name: str, raw_text: str) -> str:
        try:
            data = json.loads(raw_text)
            if isinstance(data, dict):
                if data.get("status") == "error":
                    msg = data.get("remedy") or data.get("message") or "Unknown error"
                    return f"FAILED. {msg}"
                if len(data) == 1 and "status" in data: return str(data["status"])
                return json.dumps(data)
            return raw_text
        except: return raw_text

    def _resolve_params(self, params: Any, local_results: Dict[str, Any]) -> Tuple[Any, Optional[str]]:
        if isinstance(params, str):
            pattern = r"\$([a-zA-Z0-9_-]+)(?:\[(\d+)\])?\.([a-zA-Z0-9_-]+)"
            matches = re.finditer(pattern, params)
            new_val = params
            for m in matches:
                full_match, step_key, index_str, field_name = m.group(0), m.group(1), m.group(2), m.group(3)
                if step_key not in local_results:
                    return params, f"PIPE_ERROR: Step or Alias '{step_key}' not found."
                data = local_results[step_key]
                if isinstance(data, list):
                    if not data: return params, f"PIPE_ERROR: Step '{step_key}' returned empty list."
                    idx = int(index_str) if index_str is not None else 0
                    if idx >= len(data): return params, f"PIPE_ERROR: Index [{idx}] out of bounds for '{step_key}'."
                    data = data[idx]
                elif index_str is not None:
                    return params, f"PIPE_ERROR: Index [{index_str}] used on non-list at '{step_key}'."
                if not isinstance(data, dict) or field_name not in data:
                    avail = ", ".join(data.keys()) if isinstance(data, dict) else "none"
                    return params, f"PIPE_ERROR: Field '{field_name}' not found in '{step_key}'. Available: {avail}"
                val = data[field_name]
                if params == full_match: return val, None
                new_val = new_val.replace(full_match, str(val))
            return new_val, None
        if isinstance(params, dict):
            new_dict = {}
            for k, v in params.items():
                res, err = self._resolve_params(v, local_results)
                if err: return {}, err
                new_dict[k] = res
            return new_dict, None
        if isinstance(params, list):
            new_list = []
            for item in params:
                res, err = self._resolve_params(item, local_results)
                if err: return [], err
                new_list.append(res)
            return new_list, None
        return params, None

    def _parse_result(self, text: str) -> Any:
        try:
            clean = text.strip()
            if clean.startswith("- "): clean = clean[2:]
            match = re.search(r"(\{.*\}|\[.*\])", clean, re.DOTALL)
            if match: return json.loads(match.group(1))
            return clean
        except: return text

    async def _execute_single(self, action_id: str, parameters: Dict) -> str:
        action = self.manager.get_action(action_id)
        if not action: return f"Error: Tool '{action_id}' not found."
        lid = action.groups[0] if action.groups else "root"
        landmark_ctx.set(lid)
        try:
            res, _ = await self.manager.call_action(action_id, parameters)
            return json.dumps(res) if isinstance(res, (dict, list)) else str(res)
        except Exception as e: return f"Execution Error: {str(e)}"

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
