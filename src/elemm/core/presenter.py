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
    
    def __init__(self, **kwargs):
        pass

    def present_manifest(self, 
                         landmarks: List[Landmark], 
                         instructions: str = "",
                         welcome_message: str = "",
                         hide_json: bool = False,
                         **kwargs) -> str:
        """
        Generiert das Manifest. 
        Wenn hide_json=True (High-Level-Aufruf), werden nur Root-Landmarks 
        ohne detaillierte Signaturen gezeigt (Lazy Loading).
        Wenn hide_json=False (Inspection), werden TS-Signaturen gerendert.
        """
        lines = [f"# {welcome_message}", ""]
        
        if instructions:
            lines.append("### PROTOCOL RULES")
            lines.append(instructions)
            lines.append("")

        lines.append("### MEMORY BANK (Live Memory)")
        lines.append("- Use `call_action(action='elemm:list_aliases')` to see stored findings ($step0, $step1, etc.)")
        lines.append("- PIPING: Use '$alias.field' (e.g. '$step0.hostname') to access results directly.")
        lines.append("")

        # 2. Topology / Summary Block
        # Wir zeigen die Topologie IMMER an, wenn:
        # - Wir im Summary-Modus sind (hide_json=True)
        # - Wir explizit technische Details anfordern (technical=True)
        # - Oder wenn es Sub-Landmarks gibt.
        show_topology = hide_json or kwargs.get("technical", False) or any(hasattr(lm, 'tools') and lm.tools for lm in landmarks)
        
        if show_topology:
            lines.append("### LANDMARK TOPOLOGY")
            if hide_json:
                lines.append("> [!IMPORTANT]")
                lines.append("> Use 'inspect_landmark(id)' to get technical signatures for a landmark BEFORE execution.")
            lines.append("")
            
            # Dynamische Begrenzung basierend auf max_ctx (Konfiguration)
            # Im Detail-Modus (hide_json=False) zeigen wir mehr oder alles.
            # Dynamische Begrenzung basierend auf max_ctx (Konfiguration)
            max_ctx = kwargs.get("max_ctx", 5000)
            if not hide_json:
                max_visible_tools = 1000 
            else:
                max_visible_tools = max(3, max_ctx // 1000)
            
            for lm in landmarks:
                # Header für die Landmarke
                desc = lm.description if hasattr(lm, 'description') else f"Area: {lm.id}"
                lines.append(f"- **`{lm.id}`**: {desc}")
                
                # Detail-Ansicht bei Fokus (nur 1 Landmarke)
                is_focus = len(landmarks) == 1
                
                if hasattr(lm, 'tools') and lm.tools:
                    visible_tools = lm.tools[:max_visible_tools]
                    for t in visible_tools:
                        t_desc = t.description if t.description else ""
                        # Wenn es eine Sub-Area ist (kein handler), markieren wir das
                        if not getattr(t, 'handler', None):
                            lines.append(f"  - Landmark: `{t.id}` (Area/Namespace) - {t_desc}")
                        else:
                            req_params = [f"`{p.name}`" for p in (t.parameters or []) if p.required]
                            p_str = f" (Required: {', '.join(req_params)})" if req_params else " (No required params)"
                            returns = f" -> Returns: {t.returns}" if hasattr(t, 'returns') and t.returns else ""
                            lines.append(f"  - Tool: `{t.id}`{p_str}{returns}")
                            if t_desc:
                                lines.append(f"    > {t_desc}")
                    
                    if len(lm.tools) > max_visible_tools:
                        lines.append(f"  - ... and {len(lm.tools) - max_visible_tools} more items. (Use `inspect_landmark('{lm.id}')` for more details)")
            lines.append("")
            
            # Technical JSON Block (Discovery) - Also allowed in summary if technical=True
            if kwargs.get("technical", False):
                lines.append("\n---")
                lines.append("### Technical Discovery")
                lines.append("```json-elemm")
                lines.append(json.dumps(self._get_mcp_tools(landmarks), indent=2))
                lines.append("```")
                
            return "\n".join(lines)
            
        # Inspection Mode: TS Signatures
        lines.append("### TECHNICAL SIGNATURES")
        lines.append("```typescript")
        
        for lm in landmarks:
            if lm.handler:
                lines.append(self._get_ts_sig(lm))
            for tool in (lm.tools or []):
                lines.append(self._get_ts_sig(tool))
                
        lines.append("```")
        
        # 3. Technical JSON Block (Discovery)
        if kwargs.get("technical", False):
            lines.append("\n---")
            lines.append("### Technical Discovery")
            lines.append("```json-elemm")
            lines.append(json.dumps(self._get_mcp_tools(landmarks), indent=2))
            lines.append("```")
            
        return "\n".join(lines)

    def _get_ts_sig(self, tool: Landmark) -> str:
        """Generiert eine TypeScript-Signatur für ein Tool."""
        lines = []
        
        # JSDoc Comments
        lines.append("/**")
        lines.append(f" * Tool: {tool.id}")
        # Description Filtering (Hardening)
        clean_id = tool.id.split(":")[-1].replace("_", " ").lower()
        desc = tool.description or ""
        # Check if description is basically just the ID or too short
        is_redundant = desc.lower().strip(".") == clean_id
        is_too_short = len(desc) < 5

        if tool.description and not is_redundant and not is_too_short:
            lines.append(f" * Description: {tool.description}")
        if tool.instructions:
            lines.append(f" * Instructions: {tool.instructions}")
        if tool.remedy:
            lines.append(f" * Remedy: {tool.remedy}")
        lines.append(" */")
        
        # Parameters
        params_str = "{}"
        if tool.parameters:
            param_defs = []
            for p in tool.parameters:
                ts_type = "any"
                if p.options:
                    ts_type = " | ".join([f"\"{o}\"" for o in p.options])
                elif p.type == "string": ts_type = "string"
                elif p.type in ["integer", "number"]: ts_type = "number"
                elif p.type == "boolean": ts_type = "boolean"
                elif p.type == "array": ts_type = "any[]"
                elif p.type == "object": ts_type = "Record<string, any>"
                
                req = "" if p.required else "?"
                param_defs.append(f"\n    {p.name}{req}: {ts_type};")
            
            if param_defs:
                params_str = "{" + "".join(param_defs) + "\n  }"
                
        returns_str = getattr(tool, "returns", "any") or "any"
        
        lines.append(f"function call_action(action: \"{tool.id}\", parameters: {params_str}): {returns_str};\n")
        
        return "\n".join(lines)

    def _get_mcp_tools(self, landmarks: List[Landmark]) -> List[Dict[str, Any]]:
        """Generiert technische MCP-Tool-Definitionen für Discovery-Zwecke."""
        mcp_tools = []
        for lm in landmarks:
            # Wenn es eine Area ist, nimm die Tools darunter
            targets = [lm]
            if not lm.handler and lm.tools:
                targets = lm.tools
            
            for t in targets:
                if not t.handler: continue
                
                properties = {}
                required = []
                for p in (t.parameters or []):
                    properties[p.name] = {
                        "type": p.type,
                        "description": p.description
                    }
                    if p.required:
                        required.append(p.name)
                
                mcp_tools.append({
                    "name": t.id,
                    "description": t.description,
                    "inputSchema": {
                        "type": "object",
                        "properties": properties,
                        "required": required
                    }
                })
        return mcp_tools

    def _render_landmark(self, landmark: Landmark, global_context: Optional[Dict[str, Any]] = None) -> str:
        """Alias für Kompatibilität mit mcp_server.py"""
        targets = [landmark]
        if not landmark.handler and landmark.tools:
            targets = landmark.tools
        return self.present_manifest(targets, welcome_message=f"INSPECTION: {landmark.id}", hide_json=False)
