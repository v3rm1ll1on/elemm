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
    """Renders the Elemm v2 manifest in high-fidelity Markdown and TypeScript."""
    

    def present_manifest(self, 
                         landmarks: List[Landmark], 
                         instructions: str = "",
                         welcome_message: str = "ELEMM v2 SECURE INTERFACE",
                         show_technical: bool = False,
                         is_root: bool = False,
                         **kwargs) -> str:
        """Renders the manifest in high-fidelity Markdown."""
        lines = []
        
        # 1. Header & Welcome (Root Only)
        if welcome_message:
            lines.append(f"# {welcome_message}\n")
        
        if instructions:
            lines.append(instructions)
            lines.append("\n")

        # 2. Protocol Hygiene (Memory Bank) - Root Only
        if is_root:
            lines.append("### MEMORY BANK (Live Memory)")
            lines.append("- Use `list_aliases()` to see stored findings ($step0, $step1, etc.)")
            lines.append("- PIPING: Use '$alias.field' (e.g. '$step0.hostname') to access results directly.\n")

        # 3. Landmark Topology
        lines.append("### LANDMARK TOPOLOGY\n")
        
        discovery_data = []
        offset = kwargs.get("offset", 0)
        limit_chars = kwargs.get("limit", 20000)
        
        # Calculate dynamic item limits based on char budget
        dyn_max_lm = max(20, limit_chars // 150) if limit_chars else 20
        dyn_max_tools = max(5, limit_chars // 500) if limit_chars else 5
        
        max_landmarks = kwargs.get("max_landmarks", dyn_max_lm)
        max_tools = kwargs.get("max_tools", dyn_max_tools)
        
        # Total item budget (if limit was passed, use it as a hard stop)
        item_budget = kwargs.get("max_landmarks", 99999) 
        items_rendered = 0

        if not landmarks:
            lines.append("_No landmarks discovered in this scope._")
        else:
            visible_landmarks = landmarks[offset:offset+max_landmarks]
            remaining_landmarks = len(landmarks) - (offset + max_landmarks)

            for lm in visible_landmarks:
                if items_rendered >= item_budget:
                    break
                    
                # Landmark Header
                desc = lm.description if getattr(lm, 'description', None) else f"Area: {lm.id}"
                lines.append(f"- **`{lm.id}`**: {desc}")
                items_rendered += 1
                
                # Render signature if it's an executable tool
                if getattr(lm, 'handler', None):
                    lines.append(self._render_ts_signature(lm))
                
                # Render children if it's a container area
                if hasattr(lm, 'tools') and lm.tools:
                    all_tools = lm.tools
                    # Sub-tools also count towards the budget
                    current_max_tools = min(max_tools, item_budget - items_rendered)
                    
                    if current_max_tools > 0:
                        visible_tools = all_tools[:current_max_tools]
                        remaining_tools = len(all_tools) - current_max_tools

                        for t in visible_tools:
                            t_desc = t.description or "No description"
                            if getattr(t, 'handler', None):
                                req_params = self._get_required_params_str(t)
                                lines.append(f"  - Tool: `{t.id}` ({req_params}) -> Returns: {t.returns or 'any'}")
                                lines.append(f"    > {t_desc}")
                            else:
                                lines.append(f"  - Landmark: `{t.id}` (Area/Namespace) - {t_desc}")
                            items_rendered += 1
                        
                        if remaining_tools > 0:
                            lines.append(f"  - (... and {remaining_tools} more tools. Use `inspect_landmark(landmark_id=\"{lm.id}\")` for full signatures.)")
                    else:
                        lines.append(f"  - (... tools hidden due to budget limit. Use `inspect_landmark(landmark_id=\"{lm.id}\")`.)")

                # Collect technical metadata
                if show_technical:
                    discovery_data.append({
                        "id": lm.id,
                        "description": desc,
                        "parameters": [p.model_dump() for p in getattr(lm, 'parameters', None)] if getattr(lm, 'parameters', None) else [],
                        "returns": getattr(lm, 'returns', 'any')
                    })
            
            if remaining_landmarks > 0:
                next_offset = offset + max_landmarks
                lines.append(f"\n- (... and {remaining_landmarks} more items available. **ACTION REQUIRED**: Use `_offset={next_offset}` in your next `inspect_landmark` call to fetch the next page of results.)")

        # 4. Technical Discovery Block (Nur für System-Tools)
        if show_technical and discovery_data:
            lines.append("\n---\n### Technical Discovery")
            lines.append("```json")
            lines.append(json.dumps(discovery_data, indent=2))
            lines.append("```")

        return "\n".join(lines)

    def _render_ts_signature(self, lm: Landmark) -> str:
        """Renders a clean TypeScript function signature for the tool."""
        params = lm.parameters or []
        
        # Build parameter interface or object
        if not params:
            param_str = "{}"
        else:
            p_lines = []
            for p in params:
                opt = "?" if not p.required else ""
                p_lines.append(f"{p.name}{opt}: {p.type}")
            param_str = "{ " + ", ".join(p_lines) + " }"

        returns = lm.returns or "any"
        
        ts = [
            "```typescript",
            "/**",
            f" * Tool: {lm.id}"
        ]
        
        # Hygiene: Filter redundant or too short descriptions
        desc = lm.description
        if desc:
            is_redundant = desc.lower().replace(" ", "").replace("_", "") == lm.id.lower().replace(" ", "").replace("_", "")
            is_too_short = len(desc.strip()) < 5
            if not is_redundant and not is_too_short:
                ts.append(f" * Description: {desc}")
        
        if getattr(lm, 'remedy', None):
            ts.append(f" * Remedy: {lm.remedy}")
            
        ts.extend([
            " */",
            f'function call_action(action: "{lm.id}", parameters: {param_str}): {returns};',
            "```"
        ])
        return "\n".join(ts)

    def _get_required_params_str(self, lm: Landmark) -> str:
        """Helper to get a list of required parameter names."""
        params = getattr(lm, 'parameters', []) or []
        required = [p.name for p in params if getattr(p, 'required', True)]
        if not required:
            return "No required params"
        return f"Required params: {', '.join(required)}"
