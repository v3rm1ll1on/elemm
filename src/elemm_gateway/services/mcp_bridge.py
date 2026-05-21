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

import logging
import asyncio
from contextlib import AsyncExitStack
from typing import Dict, Any, List, Optional, Tuple

from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.session import ClientSession
import mcp.types as mcp_types

from elemm.core.models import Landmark, Parameter
from elemm_gateway.services.mcp_config import MCPConfigManager

logger = logging.getLogger("elemm-gateway")

class MCPProcessManager:
    """Manages active external MCP client subprocesses as background asyncio tasks."""
    
    def __init__(self):
        self.active_sessions: Dict[str, Dict[str, Any]] = {}

    async def _run_server_loop(
        self,
        server_id: str,
        config: Dict[str, Any],
        env: Dict[str, str],
        ready_event: asyncio.Event,
        stop_event: asyncio.Event,
        result_dict: Dict[str, Any]
    ):
        """Runs the server client context manager loop inside a dedicated background task."""
        transport = config.get("transport", "stdio")
        url = config.get("url")
        
        exit_stack = AsyncExitStack()
        try:
            if transport == "sse" or url:
                if not url:
                    raise ValueError(f"SSE transport for server '{server_id}' requires a 'url' configuration.")
                
                from mcp.client.sse import sse_client
                
                # Extract headers from explicitly configured env vars
                headers = {}
                for k, v in env.items():
                    k_upper = k.upper()
                    if k_upper == "AUTHORIZATION":
                        headers["Authorization"] = v
                    elif k_upper in ("API_KEY", "API-KEY"):
                        headers["X-API-Key"] = v
                    elif k_upper in ("TOKEN", "BEARER_TOKEN") or k_upper in ("NOTION", "NOTION_TOKEN") or v.startswith("ntn_"):
                        headers["Authorization"] = v if v.startswith("Bearer ") else f"Bearer {v}"
                    else:
                        headers[k] = v
                
                # Connect via SSE client
                read_stream, write_stream = await exit_stack.enter_async_context(
                    sse_client(url, headers=headers)
                )
            else:
                server_params = StdioServerParameters(
                    command=config["command"],
                    args=config.get("args", []),
                    env=env
                )
                # Enter the stdio_client context
                read_stream, write_stream = await exit_stack.enter_async_context(
                    stdio_client(server_params)
                )
                
            # Enter the ClientSession context
            session = await exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            # Perform MCP Handshake
            await session.initialize()
            
            result_dict["session"] = session
            ready_event.set()
            
            # Run indefinitely until stopped
            await stop_event.wait()
            
        except Exception as e:
            logger.error(f"MCPProcessManager: Error in background loop for '{server_id}': {e}")
            result_dict["error"] = e
            ready_event.set()
        finally:
            await exit_stack.aclose()

    async def get_session(self, server_id: str, config: Dict[str, Any], env: Dict[str, str]) -> ClientSession:
        """Returns an active ClientSession for a server, starting it if not already running."""
        if server_id in self.active_sessions:
            conf = self.active_sessions[server_id]
            if not conf["task"].done():
                return conf["session"]
            else:
                logger.warning(f"MCPProcessManager: Server '{server_id}' background task was done/terminated. Cleaning up.")
                await self.stop_server(server_id)
            
        logger.info(f"MCPProcessManager: Starting server '{server_id}' (transport: {config.get('transport', 'stdio')}) in background task...")
        ready_event = asyncio.Event()
        stop_event = asyncio.Event()
        result_dict = {}
        
        # Start background loop
        task = asyncio.create_task(
            self._run_server_loop(server_id, config, env, ready_event, stop_event, result_dict)
        )
        
        # Wait for initialize to complete
        await ready_event.wait()
        
        if "error" in result_dict:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
            raise result_dict["error"]
            
        self.active_sessions[server_id] = {
            "session": result_dict["session"],
            "stop_event": stop_event,
            "task": task
        }
        logger.info(f"MCPProcessManager: Server '{server_id}' successfully initialized in background.")
        return result_dict["session"]

    async def stop_server(self, server_id: str):
        """Stops an active server and cleans up its resources."""
        if server_id in self.active_sessions:
            logger.info(f"MCPProcessManager: Stopping server '{server_id}'...")
            conf = self.active_sessions.pop(server_id)
            conf["stop_event"].set()
            try:
                # Give task a moment to shut down, or cancel it if needed
                await asyncio.wait_for(conf["task"], timeout=2.0)
            except asyncio.TimeoutError:
                conf["task"].cancel()
                try:
                    await conf["task"]
                except (asyncio.CancelledError, Exception):
                    pass
            except (asyncio.CancelledError, Exception) as e:
                logger.debug(f"MCPProcessManager: Background task '{server_id}' exited with: {e}")

    async def stop_all(self):
        """Stops all active servers."""
        for server_id in list(self.active_sessions.keys()):
            await self.stop_server(server_id)


class MCPBridge:
    """
    Bridge for external MCP servers. Discovers external tools, maps them
    into Elemm Landmark objects, and handles execution routing.
    """
    
    def __init__(self, config_manager: MCPConfigManager, process_manager: Optional[MCPProcessManager] = None):
        self.config_manager = config_manager
        self.process_manager = process_manager or MCPProcessManager()

    async def discover_landmarks(self, server_id: str, vault_manager: Optional[Any] = None) -> List[Landmark]:
        """
        Discovers tools on the external MCP server and translates them
        into a list of Elemm Landmark actions.
        """
        self.config_manager.reload_if_changed()
        server_conf = self.config_manager.get_server(server_id)
        if not server_conf:
            logger.warning(f"MCPBridge: Server config for '{server_id}' not found.")
            return []

        resolved_env = self.config_manager.get_resolved_env(server_id, vault_manager=vault_manager)
        
        try:
            session = await self.process_manager.get_session(server_id, server_conf, resolved_env)
            # Retrieve tools from the external server
            tools_result = await session.list_tools()
            
            landmarks = []
            remedies = server_conf.get("remedies", {})
            
            for tool in tools_result.tools:
                tool_name = tool.name
                # Hierarchy ID format: mcp:{server_id}:{tool_name}
                landmark_id = f"mcp:{server_id}:{tool_name}"
                
                # Sanitize description (some MCPs like Notion inject "Error Responses: ..." into the description)
                desc = tool.description or f"Externes Tool {tool_name} von {server_conf.get('name')}"
                if "Error Responses:" in desc:
                    desc = desc.split("Error Responses:")[0].strip()
                
                # Fetch custom remedies if configured
                remedy_info = remedies.get(tool_name, {})
                remedy_msg = None
                if isinstance(remedy_info, dict):
                    remedy_msg = remedy_info.get("on_error")
                elif isinstance(remedy_info, str):
                    remedy_msg = remedy_info

                # Parse parameter schemas
                parameters = []
                schema = tool.inputSchema or {}
                if isinstance(schema, dict):
                    props = schema.get("properties", {})
                    req = schema.get("required", [])
                    
                    for p_name, p_def in props.items():
                        parameters.append(Parameter(
                            name=p_name,
                            type=p_def.get("type", "string"),
                            description=p_def.get("description", ""),
                            required=p_name in req,
                            location="body"
                        ))

                landmarks.append(Landmark(
                    id=landmark_id,
                    type="action",
                    description=desc,
                    parameters=parameters,
                    remedy=remedy_msg,
                    meta={
                        "server_id": server_id,
                        "tool_name": tool_name,
                        "original_tool": {
                            "name": tool.name,
                            "description": tool.description,
                            "inputSchema": tool.inputSchema
                        }
                    }
                ))
            
            # Sort landmarks by ID for deterministic output
            landmarks.sort(key=lambda x: x.id)
            return landmarks
            
        except Exception as e:
            logger.error(f"MCPBridge: Failed to discover landmarks for '{server_id}': {e}")
            return []

    async def call_tool(self, server_id: str, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Executes a tool on the external MCP server and returns the raw string result."""
        server_conf = self.config_manager.get_server(server_id)
        if not server_conf:
            raise ValueError(f"Server configuration for '{server_id}' not found.")
            
        resolved_env = self.config_manager.get_resolved_env(server_id)
        session = await self.process_manager.get_session(server_id, server_conf, resolved_env)
        
        # Send call_tool request via mcp library
        resp = await session.call_tool(tool_name, arguments)
        
        # Format result to string (merges text contents)
        texts = []
        for content in resp.content:
            if hasattr(content, "text"):
                texts.append(content.text)
            elif isinstance(content, dict) and "text" in content:
                texts.append(content["text"])
        
        return "\n".join(texts)
