import asyncio
import httpx
from typing import List, Dict, Any, Callable, Optional
import mcp.types as types
from mcp.server import Server
from .base import AIProtocolManager

class LandmarkBridge:
    """
    Bridge between ELEMM Protocol and MCP Standard.
    Provides a Registry-driven Navigation interface for AI Agents.
    """
    def __init__(self, manager: Optional[AIProtocolManager] = None, base_url: str = "http://localhost:8001", server_name: str = "elemm-bridge"):
        self.manager = manager
        self.base_url = base_url
        self.server = Server(server_name)
        self.ctx = "root"
        self._lock = asyncio.Lock()
        
        # Dispatcher Mapping
        self._handlers: Dict[str, Callable] = {
            "list_navigation_points": self._handle_list_navigation_points,
            "navigate": self._handle_navigate
        }
        
        # Register handlers
        self.server.list_tools()(self.list_tools)
        self.server.call_tool()(self.call_tool)

    async def list_tools(self) -> List[types.Tool]:
        """
        Registry Style: Export core navigation tools + current module actions.
        """
        tools = [
            types.Tool(
                name="list_navigation_points",
                description="List available modules and navigation landmarks.",
                inputSchema={"type": "object", "properties": {}}
            ),
            types.Tool(
                name="navigate",
                description="Switch context to a specific module or landmark.",
                inputSchema={
                    "type": "object", 
                    "properties": {
                        "landmark_id": {"type": "string", "description": "The ID of the target module/landmark."}
                    },
                    "required": ["landmark_id"]
                }
            )
        ]

        try:
            tools_data = await self._fetch_tools_from_source()
            
            # Add module actions (excluding navigation tools which are handled via 'navigate')
            for t in tools_data:
                # Filter out internal navigation markers to keep the tool list clean
                if t.get("type") == "navigation" or "explore_" in t.get("name", ""):
                    continue
                
                # Prevent duplicates
                if any(existing.name == t.get("name") for existing in tools):
                    continue
                    
                tools.append(types.Tool(**t))
                
        except Exception:
            # Silent fail for production readiness, logging should be handled via standard logging
            pass
            
        return tools

    async def call_tool(self, name: str, arguments: dict | None) -> List[types.TextContent]:
        # Check if it's a built-in handler
        handler = self._handlers.get(name)
        if handler:
            return await handler(name, arguments or {})
            
        # Otherwise, treat as generic action
        return await self._handle_generic_action(name, arguments or {})

    async def _handle_list_navigation_points(self, _name: str, _args: dict) -> List[types.TextContent]:
        manifest = await self._fetch_manifest_from_source(group=None, agent_view=True)
        navs = manifest.get("navigation", [])
        
        if not navs:
            return [types.TextContent(type="text", text="No navigation points available in current scope.")]
            
        lines = [
            "AVAILABLE NAVIGATION POINTS:",
            "-"*30
        ]
        for n in navs:
            lines.append(f"- {n['id']}: {n.get('description')}")
            if n.get("instructions"):
                lines.append(f"  Note: {n['instructions']}")
        
        lines.append("-"*30)
        lines.append("Use 'navigate(landmark_id)' to switch your toolset context.")
        
        return [types.TextContent(type="text", text="\n".join(lines))]

    async def _handle_navigate(self, _name: str, arguments: dict) -> List[types.TextContent]:
        async with self._lock:
            lid = arguments.get("landmark_id", "")
            
            # Fetch full manifest to verify navigation point
            manifest = await self._fetch_manifest_from_source(group=None, agent_view=False)
            all_navs = manifest.get("navigation", [])
            
            # Verify if landmark exists
            nav = next((n for n in all_navs if n["id"] == lid), None)
            
            if not nav:
                # Check for legacy support or action-based landmarks
                legacy_action = next((a for a in manifest.get("actions", []) if a["id"] == lid and a.get("type") == "navigation"), None)
                if legacy_action:
                    new_ctx = legacy_action.get("opens_group") or lid
                else:
                    return [types.TextContent(
                        type="text", 
                        text=f"ERROR: Module '{lid}' not found.\nREMEDY: Use 'list_navigation_points' to see valid IDs."
                    )]
            else:
                new_ctx = lid 
            
            if lid == self.ctx:
                return [types.TextContent(type="text", text=f"Already in context: {lid}")]
                
            self.ctx = new_ctx
            return [types.TextContent(type="text", text=f"Context switched to: {new_ctx}. Your tool list has been updated.")]

    async def _handle_generic_action(self, name: str, arguments: dict) -> List[types.TextContent]:
        # SECURITY HARDENING:
        # We first check if the tool is visible in the CURRENT context or has global_access.
        # We don't just use _INTERNAL_ALL_ as a backdoor for any agent.
        
        current_tools = await self._fetch_tools_from_source()
        is_visible = any(t.get("name") == name for t in current_tools)
        
        # If not visible in current group, check if it has global access
        action = None
        if not is_visible:
            # We fetch root manifest to check for global_access=True
            root_manifest = await self._fetch_manifest_from_source(group=None, agent_view=False)
            action = next((a for a in root_manifest.get("actions", []) if a["id"] == name and a.get("global_access")), None)
            
            if not action:
                return [types.TextContent(
                    type="text", 
                    text=f"Error: Tool {name} is not available in the current context ({self.ctx}).\nREMEDY: Use 'navigate' to switch to the correct module."
                )]
        else:
            # Tool is visible, fetch its details (using internal key if manager allows it for execution)
            # We still need the full action details for execution
            manifest = await self._fetch_manifest_from_source(group="_INTERNAL_ALL_", agent_view=False)
            action = next((a for a in manifest.get("actions", []) if a["id"] == name), None)

        if not action:
            return [types.TextContent(type="text", text=f"Error: Tool {name} not found.")]
            
        # Execution logic (Local Manager or Remote URL)
        if self.manager:
            try:
                res = await self.manager.call_action(name, arguments)
                import json
                return [types.TextContent(type="text", text=json.dumps(res, indent=2))]
            except Exception as e:
                return [types.TextContent(type="text", text=f"Execution Error: {str(e)}")]
        else:
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}{action.get('url')}"
                method = action.get("method", "POST")
                
                if method == "GET":
                    resp = await client.get(url, params=arguments)
                else:
                    resp = await client.post(url, json=arguments)
                    
                return [types.TextContent(type="text", text=resp.text)]

    async def _fetch_manifest_from_source(self, group: Optional[str] = None, agent_view: bool = True) -> Dict[str, Any]:
        if self.manager:
            internal_key = self.manager.internal_access_key if group == "_INTERNAL_ALL_" else None
            return self.manager.get_manifest(group=group, agent_view=agent_view, internal_key=internal_key)
        else:
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/.well-known/llm-landmarks.json"
                params = {"agent_view": "true" if agent_view else "false"}
                if group: params["group"] = group
                
                headers = {}
                # If we are remote, we don't have the manager. Ideally the bridge should have its own internal key config.
                # For now we'll stick to the existing logic but respect the group.
                resp = await client.get(url, params=params, headers=headers)
                return resp.json()

    async def _fetch_tools_from_source(self) -> List[Dict[str, Any]]:
        if self.manager:
            return self.manager.get_mcp_tools(group=self.ctx)
        else:
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/.well-known/llm-landmarks.json"
                params = {"agent_view": "true", "group": self.ctx}
                resp = await client.get(url, params=params)
                manifest = resp.json()
                
                mcp_tools = []
                for action in manifest.get("actions", []):
                    mcp_tools.append({
                        "name": action["id"],
                        "description": action["description"],
                        "inputSchema": {
                            "type": "object",
                            "properties": {p["name"]: {"type": p["type"], "description": p.get("description", "")} for p in action.get("parameters", [])},
                            "required": [p["name"] for p in action.get("parameters", []) if p.get("required")]
                        }
                    })
                return mcp_tools

    def run_stdio(self):
        """Run the MCP server via stdio."""
        from mcp.server.stdio import stdio_server
        async def _run():
            async with stdio_server() as (read, write):
                await self.server.run(read, write, self.server.create_initialization_options())
        asyncio.run(_run())
