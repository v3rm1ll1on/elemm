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

from typing import List, Dict, Any, Optional
import json
from .models import Landmark

class ManifestPresenter:
    """Standard-Presenter für Elemm-Protokoll-Discovery."""

    def present_manifest(self, 
                         landmarks: List[Landmark], 
                         instructions: str = "", 
                         welcome_message: str = "ELEMM v2 SECURE INTERFACE", 
                         show_technical: bool = False, 
                         is_root: bool = False, 
                         **kwargs) -> str:
        """Präsentiert eine Liste von Landmarks in Markdown oder JSON."""
        
        # 1. Format Switch Check
        output_format = kwargs.get("output_format", "markdown")
        
        # 2. Hard-Facts JSON Mode (for Dashboards & Machine Processing)
        if output_format == "json":
            # EXPLORE LOGIC: If exactly one Area is requested (and it's NOT a root call), 
            # we show its children instead of itself to allow drilling down.
            if not is_root and len(landmarks) == 1 and not landmarks[0].handler and hasattr(landmarks[0], 'tools') and landmarks[0].tools:
                effective_lms = landmarks[0].tools
                parent_id = landmarks[0].id
            else:
                effective_lms = landmarks
                parent_id = None

            offset = kwargs.get("offset", 0)
            max_landmarks = kwargs.get("max_landmarks", 100) 
            
            total_count = len(effective_lms)
            paginated_lms = effective_lms[offset : offset + max_landmarks]
            
            items = []
            for lm in paginated_lms:
                item = {
                    "id": lm.id,
                    "description": lm.description,
                    "parameters": [p.model_dump() for p in (lm.parameters or [])],
                    "returns": lm.returns or "any",
                    "outputSchema": getattr(lm, 'response_schema', {}),
                    "remedy": getattr(lm, 'remedy', None),
                    "instructions": getattr(lm, 'instructions', None),
                    "is_tool": bool(lm.handler),
                }
                
                # Area/Namespace logic (Lazy Loading Hints)
                if not lm.handler and hasattr(lm, 'tools') and lm.tools:
                    item["child_count"] = len(lm.tools)
                    item["is_truncated"] = len(lm.tools) > 0 
                
                items.append(item)

            return json.dumps({
                "version": "2.0",
                "parent_id": parent_id,
                "is_root": is_root,
                "welcome_message": welcome_message if is_root else None,
                "landmarks": items,
                "pagination": {
                    "total": total_count,
                    "offset": offset,
                    "limit": max_landmarks,
                    "has_more": (offset + max_landmarks) < total_count
                }
            }, indent=2)

        # 3. Agent-Facing Markdown Mode (Default)
        lines = []
        if welcome_message:
            lines.append(f"# {welcome_message}\n")
        
        if instructions:
            lines.append(instructions + "\n")

        # Protocol Hygiene (Memory Bank) - Root Only
        if is_root:
            lines.append("### MEMORY BANK (Live Memory)")
            lines.append("- Use `list_aliases()` to see stored findings ($step0, $step1, etc.)")
            lines.append("- PIPING: Use '$alias.field' (e.g. '$step0.hostname') to access results directly.\n")

        lines.append("### LANDMARK TOPOLOGY\n")
        
        offset = kwargs.get("offset", 0)
        limit_chars = kwargs.get("limit", 20000)
        
        # Calculate dynamic item limits based on char budget for Markdown
        dyn_max_lm = max(20, limit_chars // 150) if limit_chars else 20
        max_landmarks = kwargs.get("max_landmarks", dyn_max_lm)

        if not landmarks:
            lines.append("_No landmarks discovered in this scope._")
        else:
            visible_lms = landmarks[offset : offset + max_landmarks]
            remaining_landmarks = max(0, len(landmarks) - (offset + max_landmarks))

            for lm in visible_lms:
                desc = lm.description if getattr(lm, 'description', None) else f"Area: {lm.id}"
                lines.append(f"- **`{lm.id}`**: {desc}")
                
                if hasattr(lm, 'handler') and lm.handler:
                    lines.append(self._render_ts_signature(lm))
                elif hasattr(lm, 'tools') and lm.tools:
                    # Summary for categories
                    all_tools = lm.tools
                    visible_tools = all_tools[:max(1, max_landmarks - 1)]
                    remaining_tools = len(all_tools) - len(visible_tools)
                    
                    for t in visible_tools:
                        t_desc = t.description or "No description."
                        if t.handler:
                            lines.append(f"  - Tool: `{t.id}` ({self._get_required_params_str(t)} | Returns: {t.returns or 'any'})")
                            lines.append(f"    > {t_desc}")
                        else:
                            lines.append(f"  - Landmark: `{t.id}` (Area/Namespace) - {t_desc}")
                    
                    if remaining_tools > 0:
                        lines.append(f"  - (... and {remaining_tools} more tools. Use `inspect_landmark(landmark_id=\"{lm.id}\")` for full signatures.)")

            if remaining_landmarks > 0:
                next_offset = offset + max_landmarks
                lines.append(f"\n- (... and {remaining_landmarks} more items available. **ACTION REQUIRED**: Use `_offset={next_offset}` in your next `inspect_landmark` call to fetch the next page of results.)")

        return "\n".join(lines)

    def _render_ts_signature(self, lm: Landmark) -> str:
        """Renders a clean TypeScript function signature for the tool."""
        params = lm.parameters or []
        if not params:
            param_str = "{}"
        else:
            p_lines = []
            for p in params:
                opt = "?" if not p.required else ""
                p_lines.append(f"{p.name}{opt}: {p.type}")
            param_str = "{ " + ", ".join(p_lines) + " }"

        returns = lm.returns or "any"
        ts = ["```typescript", "/**", f" * Tool: {lm.id}"]
        
        # Hygiene Filter: Skip redundant or too short descriptions
        desc = lm.description
        if desc and not self._should_skip_description(lm.id, desc):
            ts.append(f" * Description: {desc}")
            
        if getattr(lm, 'remedy', None):
            ts.append(f" * Remedy: {lm.remedy}")
            
        ts.extend([" */", f'function call_action(action: "{lm.id}", parameters: {param_str}): {returns};', "```"])
        
        # --- RESPONSE SCHEMA INJECTION ---
        schema = getattr(lm, 'response_schema', None)
        if schema and isinstance(schema, dict) and "properties" in schema:
            ts.append(self._render_schema_as_ts_interface(lm.id, schema, is_array=(lm.returns and "[]" in lm.returns)))

        return "\n".join(ts)

    def _render_schema_as_ts_interface(self, lm_id: str, schema: Dict[str, Any], is_array: bool = False) -> str:
        """Renders the response schema as a TypeScript interface for the agent."""
        props = schema.get("properties", {})
        if not props: return ""
        
        # Derive name: 'it_ops:query_node_logs' -> 'QueryNodeLogsResponse'
        base_name = lm_id.split(":")[-1].replace("_", " ").title().replace(" ", "")
        interface_name = f"{base_name}Item" if is_array else f"{base_name}Response"
        
        lines = ["```typescript", f"interface {interface_name} {{"]
        for p_name, p_info in props.items():
            p_type = p_info.get("type", "any")
            p_desc = p_info.get("description", "")
            line = f"  {p_name}: {p_type};"
            if p_desc: line += f" // {p_desc}"
            lines.append(line)
        lines.append("}")
        lines.append("```")
        return "\n".join(lines)

    def _should_skip_description(self, lm_id: str, description: str) -> bool:
        """Checks if a description is redundant or too short."""
        if not description: return True
        desc_clean = description.strip()
        if len(desc_clean) < 3: return True
        
        # Simple redundancy check (e.g. id='get_user', desc='Get user')
        norm_id = lm_id.lower().replace("_", " ").replace(":", " ").strip()
        norm_desc = desc_clean.lower().strip()
        
        if norm_id == norm_desc: return True
        # Also check without spaces
        if norm_id.replace(" ", "") == norm_desc.replace(" ", ""): return True
        
        return False

    def _get_required_params_str(self, lm: Landmark) -> str:
        """Helper to get a list of required parameter names."""
        params = getattr(lm, 'parameters', []) or []
        required = [p.name for p in params if getattr(p, 'required', True)]
        if not required:
            return "No required params"
        return f"Req: {', '.join(required)}"
