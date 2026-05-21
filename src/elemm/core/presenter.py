# Copyright (C) 2026 Marc Stöcker
# Website: https://elemm.dev
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
from .schema import SignatureGenerator

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
            max_landmarks = kwargs.get("max_landmarks", 5000) 
            
            total_count = len(effective_lms)
            paginated_lms = effective_lms[offset : offset + max_landmarks]
            
            items = []
            for lm in paginated_lms:
                item = {
                    "id": lm.id,
                    "type": lm.type,
                    "description": lm.description,
                    "parameters": [p.model_dump() for p in (lm.parameters or [])],
                    "returns": lm.returns or "any",
                    "outputSchema": getattr(lm, 'response_schema', {}),
                    "remedy": getattr(lm, 'remedy', None),
                    "instructions": getattr(lm, 'instructions', None),
                    "is_tool": bool(lm.handler) or lm.type in ["action", "tool"],
                    "meta": getattr(lm, 'meta', {})
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
                "instructions": instructions,
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
            lines.append("- AUTO-ALIASING: The system automatically assigns '$step0' (1st step), '$step1' (2nd step), etc. to each step in the sequence. You do NOT need to define manual aliases for sequential step-to-step piping.")
            lines.append("- PIPING: Use '$alias.field' (e.g. '$step0.hostname') to access results directly.")
            lines.append("- COLLISION WARNING: Avoid naming custom aliases '$stepN' (like 'step1', 'step2') as they will collide with automatic 0-based sequence indexing. Use descriptive names (e.g. 'ip_host', 'audit_account') for global persistence across turns.\n")

        lines.append("### LANDMARK TOPOLOGY\n")
        
        offset = kwargs.get("offset", 0)
        limit_chars = kwargs.get("limit", 20000)
        
        # Calculate dynamic item limits based on char budget for Markdown
        dyn_max_lm = max(20, limit_chars // 150) if limit_chars else 20
        max_landmarks = kwargs.get("max_landmarks", dyn_max_lm)

        rendered_landmarks = 0
        rendered_tools = 0

        if not landmarks:
            lines.append("_No landmarks discovered in this scope._")
        else:
            is_single_lm_drilldown = (len(landmarks) == 1 and not is_root and hasattr(landmarks[0], 'tools') and landmarks[0].tools)
            if is_single_lm_drilldown:
                visible_lms = landmarks
            else:
                visible_lms = landmarks[offset : offset + max_landmarks]
            items_rendered = 0
            for lm in visible_lms:
                if items_rendered >= max_landmarks:
                    break
                    
                if hasattr(lm, 'tools') and lm.tools:
                    total_tools = len(lm.tools)
                    estimated_cost = total_tools * 150
                    current_length = sum(len(line) for line in lines)
                    
                    # Wenn wir die Obergruppe gezielt inspizieren (len(landmarks) == 1) oder genug Budget haben und die Liste handlich ist (<= 25), blenden wir sie ein
                    if len(landmarks) == 1 or (total_tools <= 25 and (current_length + estimated_cost < limit_chars)):
                        lines.append(f"- **{lm.id}**:")
                        items_rendered += 1
                        rendered_landmarks += 1
                        
                        # Show tools but respect remaining budget and offset
                        remaining_budget = max_landmarks - items_rendered
                        if is_single_lm_drilldown:
                            visible_tools = lm.tools[offset : offset + remaining_budget]
                            hidden_tools = len(lm.tools) - (offset + len(visible_tools))
                        else:
                            visible_tools = lm.tools[:remaining_budget]
                            hidden_tools = len(lm.tools) - len(visible_tools)
                        
                        for t in visible_tools:
                            t_desc = t.description or "No description."
                            is_tool = bool(t.handler) or t.type in ["action", "tool"]
                            
                            if is_tool:
                                if show_technical:
                                    lines.append(self._render_ts_signature(t))
                                else:
                                    remedy_str = f" | Remedy: {t.remedy}" if getattr(t, 'remedy', None) else ""
                                    lines.append(f"  - Action: `{t.id}` ({self._get_required_params_str(t)} | Returns: {t.returns or 'any'}{remedy_str})")
                                    lines.append(f"    > {t_desc}")
                                rendered_tools += 1
                            else:
                                child_info = f" ({len(t.tools)} tools available in this landmark)" if hasattr(t, 'tools') and t.tools else ""
                                lines.append(f"  - Landmark: `{t.id}`{child_info}")
                                lines.append(f"    > {t_desc}")
                                rendered_landmarks += 1
                                
                            items_rendered += 1
                            
                        if hidden_tools > 0 and not is_single_lm_drilldown:
                            lines.append(f"  - (... and {hidden_tools} more tools.)")
                    else:
                        # Budget ueberschritten oder Gruppe zu gross -> nur Obergruppe listen mit Info
                        lines.append(f"- **{lm.id}** ({total_tools} tools available in this landmark)")
                        items_rendered += 1
                        rendered_landmarks += 1
                else:
                    desc = lm.description if getattr(lm, 'description', None) else f"Area: {lm.id}"
                    is_tool = bool(lm.handler) or lm.type in ["action", "tool"]
                    
                    if is_tool:
                        if show_technical:
                            lines.append(self._render_ts_signature(lm))
                        else:
                            remedy_str = f" | Remedy: {lm.remedy}" if getattr(lm, 'remedy', None) else ""
                            lines.append(f"- Action: `{lm.id}` ({self._get_required_params_str(lm)} | Returns: {lm.returns or 'any'}{remedy_str})")
                            lines.append(f"  > {desc}")
                        rendered_tools += 1
                    else:
                        lines.append(f"- **`{lm.id}`**: {desc}")
                        rendered_landmarks += 1
                        
                    items_rendered += 1

            if is_single_lm_drilldown:
                total_items = len(landmarks[0].tools)
                rendered_count = len(visible_tools)
                total_remaining = total_items - (offset + rendered_count)
                next_offset = offset + rendered_count
                has_more = total_remaining > 0
            else:
                total_items = kwargs.get("total", len(landmarks))
                total_remaining = total_items - (offset + items_rendered)
                next_offset = offset + items_rendered
                has_more = kwargs.get("has_more", total_remaining > 0)
            
            if has_more or total_remaining > 0:
                is_search = "SEARCH RESULTS FOR" in instructions
                if is_search:
                    example_lm_id = "landmark1:landmark2"
                    if landmarks:
                        first_id = landmarks[0].id
                        if ":" in first_id:
                            parts = first_id.split(":")
                            example_lm_id = ":".join(parts[:max(1, len(parts)-1)])
                        else:
                            example_lm_id = first_id
                    lines.append(f"\n- (... and {total_remaining} more items are available matching your query. **ACTION REQUIRED**: Use `_offset={next_offset}` to fetch the next page of results, or restrict your search using the `landmark_id` filter (e.g. '{example_lm_id}') to focus on a specific namespace.)")
                elif is_single_lm_drilldown:
                    lines.append(f"\n- (... and {total_remaining} more tools available. **ACTION REQUIRED**: Use `_offset={next_offset}` in your next `inspect_landmark` call to fetch the next page of results.)")
                else:
                    lines.append(f"\n- (... and {total_remaining} more items available. **ACTION REQUIRED**: Use `_offset={next_offset}` in your next `inspect_landmark` call to fetch the next page of results.)")

        # Summary footer for the agent (Guidance & Metrics)
        lines.append(f"\n**Summary**: {rendered_landmarks} landmarks | {rendered_tools} tools on this page. Use `inspect_landmark`, `call_action` or `execute_sequence` to interact.")

        return "\n".join(lines)

    def _render_ts_signature(self, lm: Landmark) -> str:
        """Renders a clean TypeScript function signature for the tool."""
        # Use central SignatureGenerator for consistency
        ts = SignatureGenerator.to_typescript_signature(lm)
        
        # Add response schema injection if available (extra formatting for agents)
        schema = getattr(lm, 'response_schema', None)
        if schema and isinstance(schema, dict) and "properties" in schema:
            ts_blocks = [ts]
            ts_blocks.append(self._render_schema_as_ts_interface(lm.id, schema, is_array=(lm.returns and "[]" in lm.returns)))
            return "\n".join(ts_blocks)

        return ts

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
        return f"REQUIRED PARAMS: {', '.join(required)}"
