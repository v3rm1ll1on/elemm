from typing import List, Optional, Union, Dict, Any
from .models import Landmark

class ManifestPresenter:
    """Renders the manifest in a domain-agnostic, structural format."""

    def __init__(self):
        pass

    def present_manifest(self, landmarks: List[Landmark], welcome_message: Optional[str] = None, instructions: Optional[str] = None, full: bool = False, skip_header: bool = False, technical: bool = False, navigation_ids: Optional[List[str]] = None) -> str:
        """Generates a structural manifest: Detailed views for navigation targets, index for others."""
        lines = []
        navigation_ids = [nid.lower() for nid in (navigation_ids or [])]
        
        if not skip_header:
            header_title = welcome_message or "SYSTEM MANIFEST"
            header = (
                f"# {header_title}\n"
                "### STRATEGY & PROTOCOL\n"
                "1. **COLLECT**: `get_manifest` for signatures.\n"
                "2. **MAP**: Identify path from landmark notes.\n"
                "3. **EXECUTE**: `execute_sequence` with piping ($alias.field).\n\n"
                "**MANDATORY**: DIRECT MCP CALLS ARE IMPOSSIBLE. Use `execute_sequence` or `call_action`.\n\n"
                "**EXAMPLES:**\n"
                "- Single: `call_action(action='namespace:id', parameters={...})`\n"
                "- Sequence: `execute_sequence(actions=[{'action': 'a:get', 'alias': 'r', ...}, {'action': 'b:set', 'parameters': {'v': '$r.v'}}]`"
            )
            lines.append(header)

        if instructions:
            lines.append(f"\n## SYSTEM INSTRUCTIONS\n{instructions}")

        # 1. Detailed Landmarks (Full/Compact Signatures)
        detailed = [l for l in landmarks if l.id.lower() in navigation_ids]
        if detailed:
            lines.append("\n## LANDMARK DIRECTORY")
            for l in detailed:
                lines.append(self._render_landmark(l, compact=True))

        # 2. Index Landmarks (Name + Description only)
        index = [l for l in landmarks if l.id.lower() not in navigation_ids]
        if index:
            lines.append("\n## OTHER AREAS (Discovery via 'inspect_landmark' required)")
            for l in index:
                if full:
                    lines.append(self._render_landmark(l))
                else:
                    lines.append(f"- **{l.id}**: {l.description}")

        if technical:
            lines.append(self.generate_technical_block(landmarks))
        
        return "\n".join(lines)

    def generate_technical_block(self, landmarks: List[Landmark]) -> str:
        """Generates the technical JSON block for discovery."""
        import json
        tools = []
        for l in landmarks:
            # Noise filtering at landmark level
            if l.id.lower() in self.noise_keys: continue
            
            actions = l.tools if l.tools else [l]
            for a in actions:
                props = {}
                required = []
                if a.parameters:
                    for p in a.parameters:
                        if p.name.lower() in self.noise_keys: continue
                        type_map = {"string": "string", "integer": "integer", "boolean": "boolean", "number": "number", "object": "object", "array": "array"}
                        props[p.name] = {
                            "type": type_map.get(p.type, "string"),
                            "description": (p.description or "").split("\n")[0][:100]
                        }
                        if p.required:
                            required.append(p.name)
                
                tools.append({
                    "name": a.id,
                    "description": (a.description or "").split("\n")[0][:200],
                    "inputSchema": {
                        "type": "object",
                        "properties": props,
                        "required": required
                    }
                })
        
        return f"\n\n----- \n### Technical Discovery\n```json-elemm\n{json.dumps(tools, indent=2)}\n```"

    def _render_landmark(self, l: Landmark, compact: bool = False) -> str:
        """Detailed view for FOCUS."""
        if compact:
            lines = [f"### AREA: {l.id.upper()}", f"> {l.description}"]
        else:
            lines = [f"## LANDMARK: {l.id.upper()}", "", f"> {l.description}", ""]
        
        actions = l.tools if l.tools else [l]
        for a in actions:
            p_list = []
            if a.parameters:
                for p in a.parameters:
                    if p.name.lower() in self.noise_keys: continue
                    req = "*" if p.required else ""
                    type_map = {"string": "str", "integer": "int", "boolean": "bool", "number": "num", "object": "obj", "array": "list"}
                    p_type = type_map.get(p.type, p.type)
                    p_list.append(f"{p.name}:{p_type}{req}")
            
            p_str = "{" + ", ".join(p_list) + "}"
            if compact:
                lines.append(f"- `{a.id}` {p_str}: {a.description}")
            else:
                lines.append(f"- Action ID: `{a.id}`")
                lines.append(f"  Parameters: {p_str}")
                lines.append(f"  Description: {a.description}")
                lines.append(f"  Usage: `call_action(action='{a.id}', parameters={{...}})`\n")
            
        return "\n".join(lines)
