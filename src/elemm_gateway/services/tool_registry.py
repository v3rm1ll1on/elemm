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

import mcp.types as types
from typing import List
from elemm.core.mcp import MCPToolFactory

class GatewayToolRegistry:
    """Registry for tools specific to the Standalone Elemm Gateway."""

    CORE_TOOL_NAMES = [
        "connect_to_site", "get_manifest", "get_landmarks", 
        "inspect_landmark", "search_landmarks", "execute_sequence", 
        "call_action", "list_aliases", "clear_session"
    ]

    @staticmethod
    def get_connect_tool() -> types.Tool:
        return types.Tool(
            name="connect_to_site",
            description="Connect to an Elemm-compliant website, OpenAPI, or GraphQL API via its URL.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to connect to (e.g., https://api.example.com/openapi.json)"}
                },
                "required": ["url"]
            }
        )

    @staticmethod
    def get_clear_session_tool() -> types.Tool:
        return types.Tool(
            name="clear_session",
            description="Clears the memory bank for a specific session ID (Privacy).",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "The session ID to clear.", "default": "default"}
                }
            }
        )

    @classmethod
    def get_all_tools(cls) -> List[types.Tool]:
        """Returns the full set of 9 tools for the Standalone Gateway."""
        core_tools = MCPToolFactory.get_core_tools(with_session=True)
        gateway_tools = [
            cls.get_connect_tool(),
            cls.get_clear_session_tool()
        ]
        # Sort or arrange them logically
        return gateway_tools + core_tools
