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
from typing import List, Dict, Any, Optional

class MCPToolFactory:
    """Central factory for standardized Elemm MCP tools."""

    @staticmethod
    def get_manifest_tool() -> types.Tool:
        return types.Tool(
            name="get_manifest",
            description="CRITICAL: Get system instructions and command topology from the active site.",
            inputSchema={
                "type": "object",
                "properties": {
                    "full": {"type": "boolean", "description": "If true, returns the complete manifest with all signatures."}
                }
            }
        )

    @staticmethod
    def call_action_tool(with_session: bool = False) -> types.Tool:
        props = {
            "action": {"type": "string", "description": "The Action ID to execute."},
            "parameters": {"type": "object", "description": "Parameters for the action."}
        }
        if with_session:
            props["session_id"] = {"type": "string", "description": "Optional session ID for memory isolation.", "default": "default"}
        
        return types.Tool(
            name="call_action",
            description="Execute a single action on the remote site. Supports hygiene (_select, _filter, _limit).",
            inputSchema={
                "type": "object",
                "properties": props,
                "required": ["action"]
            }
        )

    @staticmethod
    def execute_sequence_tool(with_session: bool = False) -> types.Tool:
        action_item = {
            "type": "object",
            "properties": {
                "action": {"type": "string"},
                "alias": {"type": "string"},
                "parameters": {"type": "object"},
                "on_error": {"type": "string", "enum": ["stop", "continue"], "default": "stop"}
            },
            "required": ["action"]
        }
        
        props = {
            "actions": {"type": "array", "items": action_item},
            "steps": {"type": "array", "description": "Alias for 'actions'.", "items": action_item}
        }
        if with_session:
            props["session_id"] = {"type": "string", "description": "Optional session ID for memory isolation.", "default": "default"}

        return types.Tool(
            name="execute_sequence",
            description="Batch execute tools. Piping: Use '$step0.field' or '$step0[0].field'. IMPORTANT: $stepN is ephemeral and relative to this call. Use 'alias' in a step to persist data globally (e.g. alias: 'my_data'). Do NOT use '.result' in paths.",
            inputSchema={
                "type": "object",
                "properties": props
            }
        )

    @staticmethod
    def list_aliases_tool(with_session: bool = False) -> types.Tool:
        props = {}
        if with_session:
            props["session_id"] = {"type": "string", "description": "The session ID to inspect.", "default": "default"}
            
        return types.Tool(
            name="list_aliases",
            description="Lists all currently stored findings (aliases) in the memory bank.",
            inputSchema={"type": "object", "properties": props}
        )

    @staticmethod
    def inspect_landmark_tool() -> types.Tool:
        return types.Tool(
            name="inspect_landmark",
            description="Returns technical TypeScript signatures for one or more landmarks. Use this BEFORE calling an action to see required parameters. Supports virtual pagination (_offset, _limit) for large namespaces.",
            inputSchema={
                "type": "object",
                "properties": {
                    "landmark_id": {
                        "oneOf": [
                            {"type": "string", "description": "A single landmark ID (e.g. 'repos')"},
                            {"type": "array", "items": {"type": "string"}, "description": "A list of landmark IDs"}
                        ]
                    },
                    "_offset": {"type": "integer", "description": "Pagination offset to skip a number of tools/landmarks."},
                    "_limit": {"type": "integer", "description": "Pagination limit to restrict the number of tools returned."}
                },
                "required": ["landmark_id"]
            }
        )

    @staticmethod
    def get_landmarks_tool() -> types.Tool:
        return types.Tool(
            name="get_landmarks",
            description="Returns a high-level summary of available landmarks/functional areas on the active site.",
            inputSchema={"type": "object", "properties": {}}
        )

    @staticmethod
    def search_landmarks_tool() -> types.Tool:
        """Returns the search_landmarks tool definition."""
        return types.Tool(
            name="search_landmarks",
            description="Searches for landmarks and tools by functional area. Supports Python REGEX. Use the pipe operator '|' for multiple terms (e.g. 'finance|bank'). DO NOT use natural language or 'OR' keywords.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Regex pattern (e.g. 'noc|it_ops' or '^remediation:.*')"},
                    "_limit": {"type": "integer", "description": "Maximum number of result items to show (Hygiene)."},
                    "_offset": {"type": "integer", "description": "Starting index for results (Virtual Pagination)."}
                },
                "required": ["query"]
            }
        )

    @classmethod
    def get_core_tools(cls, with_session: bool = False) -> List[types.Tool]:
        """Returns the set of tools available in every Elemm implementation."""
        return [
            cls.get_manifest_tool(),
            cls.call_action_tool(with_session=with_session),
            cls.execute_sequence_tool(with_session=with_session),
            cls.list_aliases_tool(with_session=with_session),
            cls.get_landmarks_tool(),
            cls.inspect_landmark_tool(),
            cls.search_landmarks_tool()
        ]
