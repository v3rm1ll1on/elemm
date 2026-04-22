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
        tools: List[Any] = None
    ) -> str:
        lines = [f"# ELEMM: {system_name}"]
        
        if instructions:
            lines.append(f"\n{instructions}")
            
        lines.append("\n### Landmarks Map:")
        for lm in landmarks:
            lid = lm.get("id", "unknown")
            notes = lm.get("notes", lm.get("description", ""))
            actions_str = ManifestGenerator._get_actions_summary(lid, tools)
            lines.append(f"- {lid}: {notes}{actions_str}")

        lines.append("\n### Navigation Strategy:")
        lines.extend([
            "1. Locate the Subsystem containing the Action you need.",
            "2. Use `inspect_landmark` to see all available tools and specific instructions for a subsystem.",
            "3. If the toolset is not in your toolbelt, use the `navigate` tool to switch context.",
            "4. Execute actions using the `execute_action` tool by providing the `action_id` and `parameters`.",
            "   (Note: Server prefixes like 'solaris-hub-' must be included when calling core tools)."
        ])
        
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
