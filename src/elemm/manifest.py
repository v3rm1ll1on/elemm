import logging
from typing import List, Dict, Any

logger = logging.getLogger("elemm-manifest")

class ManifestGenerator:
    """
    Generates a token-efficient Markdown manifest from Elemm landmarks and tools.
    """
    
    @staticmethod
    def generate_markdown(
        system_name: str,
        instructions: str,
        landmarks: List[Dict[str, Any]],
        tools: List[Any] = None,
        include_technical_metadata: bool = False
    ) -> str:
        lines = [f"# ELEMM MANIFEST: {system_name}"]
        
        if instructions:
            lines.append(f"\n> {instructions}")
            
        lines.append("\n## 🗺️ Landmarks Map")
        for lm in landmarks:
            lid = lm.get("id", "unknown")
            notes = lm.get("notes", lm.get("description", ""))
            actions_str = ManifestGenerator._get_actions_summary(lid, tools)
            lines.append(f"- **{lid}**: {notes}{actions_str}")

        lines.append("\n## 🧭 Navigation Strategy")
        lines.extend([
            "1. Use `inspect_landmark` to explore a specific subsystem.",
            "2. Use `navigate` to focus on a landmark if it's not in your current context.",
            "3. Use `execute_action` for functional tasks."
        ])

        if include_technical_metadata and tools:
            import json
            # We embed the technical MCP definitions in a hidden-ish block
            lines.append("\n---")
            lines.append("### 🛠️ Technical Discovery (Machine Readable)")
            lines.append("```json-elemm")
            # We need the full MCP definitions here
            mcp_data = []
            if tools:
                # Assuming tools are already in MCP format or we convert them here
                # For simplicity, we assume they are provided as dicts
                mcp_data = tools
            lines.append(json.dumps(mcp_data, indent=2))
            lines.append("```")
        
        return "\n".join(lines)

    @staticmethod
    def _get_actions_summary(landmark_id: str, tools: List[Any], limit: int = 3) -> str:
        if not tools:
            return ""
            
        landmark_tools = []
        for t in tools:
            # Handle both dict and object access
            groups = t.get("groups", []) if isinstance(t, dict) else getattr(t, "groups", [])
            if landmark_id in groups or (landmark_id == "root" and not groups):
                landmark_tools.append(t)
        
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
            return "\n".join(header + ["_No tools registered in this landmark._"])
            
        tool_lines = [f"- **{t.get('id', t.get('name'))}**: {t.get('description', '')}" for t in tools]
        return "\n".join(header + tool_lines)
