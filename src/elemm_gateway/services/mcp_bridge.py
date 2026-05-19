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
from contextlib import AsyncExitStack
from typing import Dict, Any, List, Optional, Tuple

from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.session import ClientSession
import mcp.types as mcp_types

from elemm.core.models import Landmark, Parameter
from elemm_gateway.services.mcp_config import MCPConfigManager

logger = logging.getLogger("elemm-gateway")

class MCPProcessManager:
    """Manages active external MCP client subprocesses and persistent sessions."""
    
    def __init__(self):
        self.active_sessions: Dict[str, Tuple[ClientSession, AsyncExitStack]] = {}

    async def get_session(self, server_id: str, config: Dict[str, Any], env: Dict[str, str]) -> ClientSession:
        """Returns an active ClientSession for a server, starting it if not already running."""
        if server_id in self.active_sessions:
            session, _ = self.active_sessions[server_id]
            return session
            
        logger.info(f"MCPProcessManager: Starting server '{server_id}'...")
        exit_stack = AsyncExitStack()
        try:
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
            
            self.active_sessions[server_id] = (session, exit_stack)
            logger.info(f"MCPProcessManager: Server '{server_id}' successfully initialized.")
            return session
        except Exception as e:
            await exit_stack.aclose()
            logger.error(f"MCPProcessManager: Failed to start server '{server_id}': {e}")
            raise e

    async def stop_server(self, server_id: str):
        """Stops an active server and cleans up its resources."""
        if server_id in self.active_sessions:
            logger.info(f"MCPProcessManager: Stopping server '{server_id}'...")
            _, exit_stack = self.active_sessions.pop(server_id)
            await exit_stack.aclose()

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

    async def discover_landmarks(self, server_id: str) -> List[Landmark]:
        """
        Discovers tools on the external MCP server and translates them
        into a list of Elemm Landmark actions.
        """
        self.config_manager.reload_if_changed()
        server_conf = self.config_manager.get_server(server_id)
        if not server_conf:
            logger.warning(f"MCPBridge: Server config for '{server_id}' not found.")
            return []

        resolved_env = self.config_manager.get_resolved_env(server_id)
        
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
                    description=tool.description or f"Externes Tool {tool_name} von {server_conf.get('name')}",
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
