# This file is part of Elemm.
#
# Elemm is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Elemm is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Elemm.  If not, see <https://www.gnu.org/licenses/>.

import logging
from typing import List, Dict, Any

logger = logging.getLogger("elemm-manifest")

class ManifestGenerator:
    """
    Generates a token-efficient Markdown manifest from Elemm landmarks and tools.
    """
    
    @staticmethod
    def generate_markdown(
        manager: Any = None,
        system_name: str = "Elemm System",
        instructions: str = "",
        landmarks: List[Dict[str, Any]] = None,
        tools: List[Dict[str, Any]] = None,
        include_technical_metadata: bool = False,
        parts: List[str] = None,
        is_root: bool = True,
        **kwargs
    ) -> str:
        lines = []
        # If no parts specified, determine based on is_root
        if parts is None:
            # Navigation Strategy (instructions) should ALWAYS be visible when landmarks are listed
            if is_root:
                requested = ["welcome", "instructions", "landmarks"]
            else:
                requested = ["instructions", "landmarks"] # Show local instructions in sub-landmarks
        else:
            requested = parts
        
        if "welcome" in requested or "title" in requested:
            lines.append(f"# ELEMM MANIFEST: {system_name}")
            
        if "instructions" in requested and instructions:
            lines.append(f"
### AGENT DIRECTIVE
{instructions}")
            
        # Optimize: Group actions by landmark once before the loop
        actions_by_group = {}
        all_actions = (manager.actions if manager and hasattr(manager, "actions") else (tools or []))
        for a in all_actions:
            groups = (a.get("groups", []) if isinstance(a, dict) else getattr(a, "groups", []))
            for g in groups:
                if g not in actions_by_group: actions_by_group[g] = []
                actions_by_group[g].append(a)
            if not groups:
                if "root" not in actions_by_group: actions_by_group["root"] = []
                actions_by_group["root"].append(a)

        if "landmarks" in requested and landmarks:
            if lines: lines.append("") # Spacer
            lines.append("## Landmarks Map")
            for landmark in landmarks:
                l_id = landmark.get("id")
                l_notes = landmark.get("notes") or landmark.get("description", "")
                
                # Use pre-grouped actions
                landmark_tools = actions_by_group.get(l_id, [])
                summary = ManifestGenerator._get_summary_string(landmark_tools) if landmark_tools else ""
                lines.append(f"- **{l_id}**: {l_notes}{summary}")
        elif tools:
            lines.append("
## Available Tools (Flat View)")
            for t in tools:
                # Robustly handle both object and dict types
                if isinstance(t, dict):
                    tid = t.get("id") or t.get("name", "unknown")
                    desc = t.get("description", "").split("
")[0]
                else:
                    tid = getattr(t, "id", getattr(t, "name", "unknown"))
                    desc = getattr(t, "description", "").split("
")[0]
                lines.append(f"- **{tid}**: {desc}")

        if include_technical_metadata:
            import json
            # We embed the technical MCP definitions in a hidden-ish block for Gateways/Bridges
            lines.append("
---")
            lines.append("### Technical Discovery (Machine Readable)")
            lines.append("> [!NOTE]")
            lines.append("> This block contains the full technical definitions for Elemm Gateways.")
            lines.append("```json-elemm")
            
            # Use provided tools or extract from manager
            mcp_data_raw = tools or (manager.actions if manager and hasattr(manager, "actions") else [])
            from ..core.discovery import convert_actions_to_mcp_tools
            mcp_data = convert_actions_to_mcp_tools(mcp_data_raw)
            
            lines.append(json.dumps([t.model_dump() for t in mcp_data], indent=2))
            lines.append("```")
        
        return "
".join(lines)

    @staticmethod
    def _get_summary_string(landmark_tools: List[Any], limit: int = 3) -> str:
        action_ids = []
        for t in landmark_tools:
            aid = t.get("id") or t.get("name") if isinstance(t, dict) else getattr(t, "id", getattr(t, "name", None))
            if aid:
                action_ids.append(aid)

        if not action_ids:
            return ""
            
        summary = ", ".join(action_ids[:limit])
        if len(action_ids) > limit:
            summary += f", ... (+{len(action_ids) - limit} more)"
        return f" (Actions: {summary})"

    @staticmethod
    def generate_detailed_landmark(landmark_id: str, tools: List[Dict[str, Any]]) -> str:
        header = [f"# LANDMARK DETAILS: {landmark_id}", "", "### Available Tools"]
        if not tools:
            return "
".join(header + ["_No tools registered in this landmark._"])
            
        tool_lines = [f"- **{t.get('id', t.get('name'))}**: {t.get('description', '')}" for t in tools]
        return "
".join(header + tool_lines)
