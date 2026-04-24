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
            lines.append(f"""
 ### AGENT DIRECTIVE
 {instructions}""")
            
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
                summary = ManifestGenerator._get_summary_string(l_id, landmark_tools) if landmark_tools else ""
                lines.append(f"- **{l_id}**: {l_notes}{summary}")
        elif tools:
            lines.append("\n## Available Tools (Flat View)")
            for t in tools:
                # Robustly handle both object and dict types
                if isinstance(t, dict):
                    tid = t.get("id") or t.get("name", "unknown")
                    desc = t.get("description", "").split("\n")[0]
                else:
                    tid = getattr(t, "id", getattr(t, "name", "unknown"))
                    desc = getattr(t, "description", "").split("\n")[0]
                lines.append(f"- **{tid}**: {desc}")

        if include_technical_metadata:
            import json
            # We embed the technical MCP definitions in a hidden-ish block for Gateways/Bridges
            lines.append("\n---")
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
        
        return "\n".join(lines)

    @staticmethod
    def _get_summary_string(l_id: str, landmark_tools: List[Any], limit: int = 10) -> str:
        action_ids = []
        is_noise_landmark = True
        
        for t in landmark_tools:
            aid = t.get("id") or t.get("name") if isinstance(t, dict) else getattr(t, "id", getattr(t, "name", None))
            if not aid:
                continue
                
            # THE SMART HOT-SIGNAL: A tool is 'Hot' if it has protocol metadata (Remedy/Instructions)
            remedy = (t.get("remedy") or "") if isinstance(t, dict) else (getattr(t, "remedy", "") or "")
            instr = (t.get("instructions") or "") if isinstance(t, dict) else (getattr(t, "instructions", "") or "")
            desc = (t.get("description", "") if isinstance(t, dict) else getattr(t, "description", "")).lower()
            
            # If it has a remedy, instructions, or a non-generic description, it's NOT noise
            if remedy or instr or ("internal operation" not in desc and desc != ""):
                is_noise_landmark = False

            # Get parameters for compact signature
            params = t.get("parameters") if isinstance(t, dict) else getattr(t, "parameters", [])
            param_names = [p.name if hasattr(p, "name") else p.get("name") for p in params] if params else []
            p_str = f"({', '.join(param_names)})" if param_names else "()"
            
            hint = ""
            if remedy:
                hint = f" [REQ: {str(remedy).split('.')[0].strip()}]"
            elif instr:
                hint = f" [DEP: {str(instr).split('.')[0].strip() if '.' in str(instr) else str(instr).split('(')[0].strip()}]"
            
            action_ids.append(f"{l_id}.{aid}{p_str}{hint}")

        if not action_ids:
            return ""
            
        # NOISE SUPPRESSION: Collapse pure background landmarks
        if is_noise_landmark and len(action_ids) > 2:
            return f"\n  └─ {len(action_ids)} maintenance tools (hidden)"

        summary_lines = []
        for aid in action_ids[:limit]:
            summary_lines.append(f"\n  └─ {aid}")
            
        if len(action_ids) > limit:
            summary_lines.append(f"\n  └─ ... (+{len(action_ids) - limit} more). Call 'navigate' to explore this landmark.")
            
        return "".join(summary_lines)

    @staticmethod
    def generate_detailed_landmark(landmark_id: str, tools: List[Dict[str, Any]]) -> str:
        header = [f"# LANDMARK DETAILS: {landmark_id}", "", "### Available Tools"]
        if not tools:
            return "\n".join(header + ["_No tools registered in this landmark._"])
            
        tool_lines = [f"- **{t.get('id', t.get('name'))}**: {t.get('description', '')}" for t in tools]
        return "\n".join(header + tool_lines)
