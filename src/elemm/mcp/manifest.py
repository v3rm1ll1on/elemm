from typing import List, Dict, Any, Optional, Union
import json
import re

class ManifestGenerator:
    def __init__(self, manager):
        self.manager = manager

    def generate_summary(self) -> str:
        """Returns a System Map: Landmarks + their Tool IDs."""
        lines = ["# ELEMM SYSTEM DIRECTORY", ""]
        lines.append("### USAGE")
        lines.append("- **BROWSE**: Use `get_landmarks` to find the right area.")
        lines.append("- **FOCUS**: Use `inspect_landmark(id)` to load full signatures for an area.")
        lines.append("- **EXECUTE**: Use `execute_sequence` for multi-step tasks.\n")
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
        """Returns the COMPLETE manifest: all landmarks with all tool signatures."""
        all_ids = []
        for l in self.manager.landmarks:
            is_dict = isinstance(l, dict)
            l_id = l.get("id") if is_dict else getattr(l, "id", "unknown")
            all_ids.append(l_id)
        
        return self.generate_landmark_detail(all_ids)

    def generate_landmark_detail(self, landmark_ids: Union[str, List[str]]) -> str:
        """Returns detailed tool signatures for one or more landmarks."""
        if not landmark_ids: return "Error: No landmark_ids provided."
        
        ids = [landmark_ids] if isinstance(landmark_ids, str) else landmark_ids
        landmarks = self.manager.landmarks
        
        final_sections = [
            "# ELEMM MISSION PROTOCOL & FULL MANIFEST",
            "",
            "### STRATEGY: ONE-SHOT RESOLUTION",
            "1. **COLLECT**: Use 'get_manifest' to load all technical signatures.",
            "2. **MAP**: Identify the resolution path based on landmark notes below.",
            "3. **EXECUTE**: Use 'execute_sequence' with piping ($alias.field) for 100% success.",
            "4. **FALLBACK**: If sequence piping fails repeatedly, abandon the sequence and use 'call_action' sequentially.",
            "NOTE: Hallucinating IDs is strictly prohibited. Resolve all values first.",
            ""
        ]
        
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
                lines.append("- No tools.")
            else:
                lines.append("⚠️ CRITICAL: The items below are ACTION IDs, NOT direct MCP tools! You MUST pass them to 'call_action' or 'execute_sequence'!\n")
                for a in actions:
                    p_list = []
                    
                    # Merge parameters and payload, deduplicating by name
                    seen_params = {}
                    all_params = (getattr(a, "parameters", []) or [])
                    if getattr(a, "payload", None):
                        all_params += a.payload
                        
                    for p in all_params:
                        if p.name not in seen_params or getattr(p, 'required', False):
                            seen_params[p.name] = p
                            
                    for p in seen_params.values():
                        req_str = "(REQUIRED)" if p.required else "(optional)"
                        p_list.append(f"'{p.name}': {p.type} {req_str}")
                    
                    p_str = "{" + ", ".join(p_list) + "}"
                    
                    # Extract Response Fields
                    r_display = ""
                    schema = getattr(a, "response_schema", {})
                    if schema:
                        if schema.get("type") == "object":
                            r_display = " -> Returns: {" + ", ".join(schema.get("properties", {}).keys()) + "}"
                        elif schema.get("type") == "array":
                            r_display = " -> Returns: List[...]"

                    clean_desc = (a.description or "").split("\n")[0][:80]
                    lines.append(f"- Action ID: `{a.id}`\n  Parameters: {p_str}{r_display}\n  Description: {clean_desc}\n")
            
            final_sections.append("\n".join(lines))
            
        return "\n\n---\n\n".join(final_sections)

    def generate_technical_block(self, landmark_ids: Optional[Union[str, List[str]]] = None) -> str:
        """Returns the technical json-elemm block for tool mirroring."""
        actions = self.manager.actions
        if landmark_ids:
            ids = [landmark_ids] if isinstance(landmark_ids, str) else landmark_ids
            actions = [a for a in actions if any(lid in getattr(a, "groups", []) for lid in ids)]
        else:
            # Default to 'root' (global) tools only to avoid manifest bloat
            actions = [a for a in actions if not getattr(a, "groups", [])]
        mcp_tools = []
        for a in actions:
            # Flatten parameters and payload into a single MCP inputSchema
            properties = {}
            required = []
            
            all_params = (getattr(a, "parameters", []) or []) + (getattr(a, "payload", []) or [])
            if isinstance(getattr(a, "payload", None), dict):
                # Handle dict payload (already a schema)
                properties.update(a.payload)
            else:
                for p in all_params:
                    p_name = getattr(p, "name", "param")
                    properties[p_name] = {
                        "type": getattr(p, "type", "string"),
                        "description": getattr(p, "description", "")
                    }
                    if getattr(p, "required", True):
                        required.append(p_name)

            mcp_tools.append({
                "name": a.id,
                "description": a.description or f"Execute {a.id}",
                "inputSchema": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            })
            
        return f"\n\n---\n### Technical Discovery\n```json-elemm\n{json.dumps(mcp_tools, indent=2)}\n```"

    def _get_fields_display(self, schema: Dict[str, Any]) -> str:
        """Returns a string representation of the schema fields with compact descriptions."""
        if not schema or not isinstance(schema, dict):
            return ""
            
        s_type = schema.get("type")
        
        # 1. Array handling
        if s_type == "array" or "items" in schema:
            inner = self._get_fields_display(schema.get("items", {}))
            return f"[{inner}]" if inner else "[]"
            
        # 2. Object handling
        props = schema.get("properties", {})
        if not props:
            if "properties" not in schema and s_type == "object":
                return "{...}"
            return ""
            
        field_strs = []
        for k, v in props.items():
            desc = v.get("description")
            # Compact description: only take first 20 chars and remove 'The ', 'A ' etc.
            if desc:
                clean_desc = re.sub(r"^(the|a|an)\s+", "", str(desc), flags=re.IGNORECASE)
                field_strs.append(f"{k}: {clean_desc[:25]}")
            else:
                field_strs.append(k)
            
        return f"{{{', '.join(field_strs)}}}"
