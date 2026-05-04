from typing import List, Dict, Any, Optional, Union
import json
import re

class ManifestGenerator:
    def __init__(self, manager, noise_keys: Optional[List[str]] = None):
        self.manager = manager
        self.noise_keys = [k.lower() for k in (noise_keys or [])]

    def generate_summary(self) -> str:
        """Returns a System Map: Landmarks + their Tool IDs."""
        lines = ["# ELEMM SYSTEM DIRECTORY", ""]
        lines.append("- **BROWSE**: `get_landmarks` for areas.")
        lines.append("- **FOCUS**: `inspect_landmark(id)` for signatures.")
        lines.append("- **EXECUTE**: `execute_sequence` for tasks.\n")
        lines.append("## Landmarks & Tool Index")
        
        landmarks = self.manager.landmarks
        for l in landmarks:
            is_dict = isinstance(l, dict)
            lid = l.get("id") if is_dict else getattr(l, "id", "unknown")
            desc = (l.get("notes") or l.get("description", "")) if is_dict else (getattr(l, "notes", "") or getattr(l, "description", ""))
            
            # Find tool IDs for this landmark
            t_ids = [a.id for a in self.manager.actions if lid in getattr(a, "groups", [])]
            t_str = f"Tools: [{', '.join(t_ids)}]" if t_ids else "No tools."
            
            lines.append(f"- **{lid}**: {desc}")
            lines.append(f"  {t_str}")
            
        return "\n".join(lines)

    def generate_full(self) -> str:
        """Returns a SMART manifest: full details for essential landmarks, summaries for others."""
        landmarks = self.manager.landmarks
        official_ids = {str(l.get("id") if isinstance(l, dict) else getattr(l, "id", "")).strip().lower() for l in self.manager.navigation_landmarks}
        
        header = (
            "# ELEMM MANIFEST\n"
            "### STRATEGY: ONE-SHOT\n"
            "1. **COLLECT**: `get_manifest` for signatures.\n"
            "2. **MAP**: Identify path from landmark notes.\n"
            "3. **EXECUTE**: `execute_sequence` with piping. IMPORTANT: Use `$alias.field` (not just `$alias`).\n"
            "NOTE: No hallucinated IDs. Resolve values first.\n"
        )
        sections = [header]
        
        # 1. Essential Landmarks (Full Details)
        essential_ids = [str(l.get("id") if isinstance(l, dict) else getattr(l, "id", "")) for l in landmarks if str(l.get("id") if isinstance(l, dict) else getattr(l, "id", "")).lower() in official_ids]
        if essential_ids:
            sections.append(self.generate_landmark_detail(essential_ids, include_header=False))
            
        # 2. Secondary/Noise Landmarks (Summary Only)
        other_landmarks = [l for l in landmarks if str(l.get("id") if isinstance(l, dict) else getattr(l, "id", "")).lower() not in official_ids]
        if other_landmarks:
            sections.append("\n## ADDITIONAL LANDMARKS (Discovery Required)")
            sections.append("> Use `inspect_landmark(id)` to load parameter schemas for these areas.\n")
            for l in other_landmarks:
                lid = l.get("id") if isinstance(l, dict) else getattr(l, "id", "unknown")
                t_ids = [a.id for a in self.manager.actions if lid in getattr(a, "groups", [])]
                sections.append(f"- **{lid}**: {len(t_ids)} tools available.")
                
        return "\n".join(sections)

    def generate_landmark_detail(self, landmark_ids: Union[str, List[str]], include_header: bool = True) -> str:
        """Returns detailed tool signatures for one or more landmarks."""
        if not landmark_ids: return "Error: No landmark_ids provided."
        
        ids = [landmark_ids] if isinstance(landmark_ids, str) else landmark_ids
        landmarks = self.manager.landmarks
        
        final_sections = []
        if include_header:
            header = (
                "# ELEMM MANIFEST\n"
                "### STRATEGY: ONE-SHOT\n"
                "1. **COLLECT**: `get_manifest` for signatures.\n"
                "2. **MAP**: Identify path from landmark notes.\n"
                "3. **EXECUTE**: `execute_sequence` with piping. IMPORTANT: Use `$alias.field` (not just `$alias`).\n"
                "NOTE: No hallucinated IDs. Resolve values first.\n"
            )
            final_sections.append(header)
        
        for lid in ids:
            target_id = str(lid).strip().lower()
            landmark = None
            for l in landmarks:
                curr_id = str(l.get("id") if isinstance(l, dict) else getattr(l, "id", "")).strip().lower()
                if curr_id == target_id:
                    landmark = l
                    break
            
            if not landmark:
                final_sections.append(f"### Landmark '{lid}' NOT FOUND")
                continue

            lines = [f"## LANDMARK: {lid.upper()}", ""]
            l_desc = (landmark.get("notes") or landmark.get("description", "")) if isinstance(landmark, dict) else (getattr(landmark, "notes", "") or getattr(landmark, "description", ""))
            if l_desc: lines.append(f"> {l_desc}\n")

            actions = [a for a in self.manager.actions if lid in getattr(a, "groups", [])]
            if not actions:
                lines.append("- No tools available for this landmark.")
            else:
                lines.append("### ⚠️ MANDATORY EXECUTION PROTOCOL\n"
                             "**DIRECT MCP CALLS ARE IMPOSSIBLE.** The tools listed below are NOT direct MCP functions.\n"
                             "- To run ONE tool: Use `call_action(action='ID', parameters={...})`.\n"
                             "- To run MANY tools: Use `execute_sequence` (High Performance).\n"
                             "Failure to use these will result in 'Tool Not Found' errors!\n")
                for a in actions:
                    p_list = []
                    
                    seen_params = {}
                    all_params = (getattr(a, "parameters", []) or [])
                    if getattr(a, "payload", None):
                        all_params += a.payload
                        
                    for p in all_params:
                        if p.name.lower() in self.noise_keys: continue
                        if p.name not in seen_params or getattr(p, 'required', False):
                            seen_params[p.name] = p
                            
                    type_map = {"string": "str", "integer": "int", "boolean": "bool", "number": "num", "object": "obj", "array": "list"}
                    for p in seen_params.values():
                        req = "*" if p.required else ""
                        p_type = type_map.get(p.type, p.type)
                        p_list.append(f"{p.name}:{p_type}{req}")
                    
                    p_str = "{" + ", ".join(p_list) + "}"
                    
                    # Extract Response Fields
                    r_display = ""
                    schema = getattr(a, "response_schema", {})
                    if schema:
                        if schema.get("type") == "object":
                            props = list(schema.get("properties", {}).keys())
                            # Filter noise from response schema display
                            props = [p for p in props if p.lower() not in self.noise_keys]
                            if len(props) > 12:
                                props = props[:12] + ["..."]
                            r_display = " -> Returns: {" + ", ".join(props) + "}"
                        elif schema.get("type") == "array":
                            r_display = " -> Returns: list"
                    
                    desc_text = (a.description or "").split("\n")[0].strip()
                    # Skip description if it's just a repeat of the ID (case-insensitive)
                    id_words = a.id.replace("_", " ").lower()
                    is_redundant = desc_text.lower().startswith(id_words) or len(desc_text) < 5
                    clean_desc = f"\n  Description: {desc_text[:80]}" if not is_redundant else ""
                    
                    lines.append(f"- Action ID: `{a.id}`\n  Parameters: {p_str}{r_display}{clean_desc}\n")
            
            final_sections.append("\n".join(lines))
            
        return "\n\n---\n\n".join(final_sections)

    def generate_technical_block(self, landmark_ids: Optional[Union[str, List[str]]] = None) -> str:
        """Returns a technical JSON block for remote discovery (Gateway-compatible)."""
        ids = [landmark_ids] if isinstance(landmark_ids, str) else (landmark_ids or [])
        actions = self.manager.actions
        
        if ids:
            actions = [a for a in actions if any(lid in getattr(a, "groups", []) for lid in ids)]
        
        technical_tools = []
        for a in actions:
            # Aggregate parameters and payload
            all_params = (getattr(a, "parameters", []) or [])
            if getattr(a, "payload", None):
                all_params += a.payload
            
            # Use noise filter
            props = {}
            required = []
            for p in all_params:
                if p.name.lower() in self.noise_keys: continue
                props[p.name] = {
                    "type": p.type or "string",
                    "description": (p.description or "").split("\n")[0][:100]
                }
                if getattr(p, "required", False):
                    required.append(p.name)

            technical_tools.append({
                "name": a.id,
                "description": (a.description or "").split("\n")[0][:200],
                "inputSchema": {
                    "type": "object",
                    "properties": props,
                    "required": required
                }
            })
        
        return f"\n\n---\n### Technical Discovery\n```json-elemm\n{json.dumps(technical_tools, indent=2)}\n```"

    def _get_fields_display(self, schema: Dict[str, Any]) -> str:
        return "" # Deprecated
