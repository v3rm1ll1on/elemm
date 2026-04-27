from typing import List, Dict, Any, Optional, Union
import json
import re

class ManifestGenerator:
    def __init__(self, manager):
        self.manager = manager

    def generate_summary(self) -> str:
        """Returns a high-level summary of all landmarks."""
        lines = ["# ELEMM REGISTRY: Landmarks Summary", ""]
        lines.append("### DIRECTIVE")
        lines.append("1. DISCOVER: Call 'inspect_landmark(id)' to see tools for a namespace.")
        lines.append("2. EXECUTE: Call 'execute_sequence' for multi-step tasks.\n")
        lines.append("## Available Landmarks")
        
        landmarks = self.manager.landmarks
        for l in landmarks:
            is_dict = isinstance(l, dict)
            l_id = l.get("id") if is_dict else getattr(l, "id", "unknown")
            l_desc = (l.get("notes") or l.get("description", "")) if is_dict else (getattr(l, "notes", "") or getattr(l, "description", ""))
            lines.append(f"- **{l_id}**: {l_desc}")
            
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
        
        final_sections = []
        
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

            lines = [f"## LANDMARK: {lid}", ""]
            l_desc = (landmark.get("notes") or landmark.get("description", "")) if isinstance(landmark, dict) else (getattr(landmark, "notes", "") or getattr(landmark, "description", ""))
            if l_desc: lines.append(f"> {l_desc}\n")

            actions = [a for a in self.manager.actions if lid in getattr(a, "groups", [])]
            if not actions:
                lines.append("- No tools available.")
            else:
                for a in actions:
                    # Robust Param Extraction
                    p_list = []
                    params = getattr(a, "parameters", []) or []
                    for p in params:
                        p_name = getattr(p, "name", "param")
                        p_required = getattr(p, "required", True)
                        p_list.append(f"{p_name}{'' if p_required else '?'}")
                    
                    p_str = ", ".join(p_list)
                    type_tag = "[W]" if any(w in a.id.lower() for w in ["set", "update", "delete", "post", "quarantine", "restart", "secure", "submit"]) else "[R]"
                    
                    # Extract Response Fields for Piping
                    r_display = self._get_fields_display(getattr(a, "response_schema", {}))
                    r_str = f" -> {r_display}" if r_display else ""
                    
                    lines.append(f"- {type_tag} **{a.id}**({p_str}){r_str}")
                    if a.description:
                        lines.append(f"  * {a.description}")
                    
                    remedy = getattr(a, "remedy", None)
                    if remedy:
                        lines.append(f"  * [REMEDY: {remedy}]")
            
            final_sections.append("\n".join(lines))
            
        return "\n\n---\n\n".join(final_sections)

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
