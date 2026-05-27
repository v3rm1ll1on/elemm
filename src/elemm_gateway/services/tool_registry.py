# Copyright (C) 2026 Marc Stöcker
# Website: https://elemm.dev
#
# This program is licensed under the Business Source License 1.1 (BSL 1.1).
# See the LICENSE file in the root directory for details.

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