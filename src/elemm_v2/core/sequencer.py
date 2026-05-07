import re
import json
from typing import Any, Dict, List, Optional, Tuple

class PipeResolver:
    """Resolves $alias.field placeholders in objects."""
    
    # Erkennt $alias.field oder $alias[0].field innerhalb von Strings
    PATTERN = re.compile(r"\$?([a-zA-Z0-9_-]+)(?:\[(\d+)\])?\.([a-zA-Z0-9_-]+)")

    @classmethod
    def resolve(cls, data: Any, context: Dict[str, Any]) -> Tuple[Any, Optional[str]]:
        """Recursively resolves placeholders in data using the context."""
        if isinstance(data, str):
            # 1. Prüfen, ob der gesamte String ein Platzhalter ist (für typgetreue Rückgabe)
            full_match = cls.PATTERN.fullmatch(data.strip("$"))
            if not full_match:
                # Falls kein Full-Match, versuche wir re.sub für eingebettete Strings
                def replacer(match):
                    alias, index, field = match.groups()
                    if alias in context:
                        source = context[alias]
                        if index is not None and isinstance(source, list):
                            idx = int(index)
                            if idx < len(source): source = source[idx]
                        elif isinstance(source, list) and source:
                            source = source[0]
                        
                        if isinstance(source, dict) and field in source:
                            return str(source[field])
                    return match.group(0) # Unverändert lassen bei Fehler
                
                return cls.PATTERN.sub(replacer, data), None

            # 2. Falls Full-Match: Typgetreue Auflösung (z.B. Dict zurückgeben)
            alias, index, field = full_match.groups()
            if alias not in context:
                return data, f"Alias '{alias}' not found."
            
            source = context[alias]
            if index is not None:
                if not isinstance(source, list): return data, f"'{alias}' is not a list."
                idx = int(index)
                if idx >= len(source): return data, f"Index [{idx}] out of bounds for '{alias}'."
                source = source[idx]
            elif isinstance(source, list):
                if not source: return data, f"'{alias}' is an empty list."
                # v1 Genius: Automatisch Index 0 nehmen, wenn kein Index angegeben
                source = source[0]

            if not isinstance(source, dict) or field not in source:
                avail = ", ".join(source.keys()) if isinstance(source, dict) else "none"
                return data, f"Field '{field}' in '{alias}' not found. Available: {avail}"
            
            return source[field], None

        if isinstance(data, dict):
            new_dict = {}
            for k, v in data.items():
                res, err = cls.resolve(v, context)
                if err: return data, err
                new_dict[k] = res
            return new_dict, None

        if isinstance(data, list):
            new_list = []
            for item in data:
                res, err = cls.resolve(item, context)
                if err: return data, err
                new_list.append(res)
            return new_list, None

        return data, None

class SequenceEngine:
    """Executes a chain of actions and manages state (v1 Enhanced)."""
    
    def __init__(self, manager):
        self.manager = manager

    async def run(self, actions: List[Dict[str, Any]], initial_context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        context = initial_context or {}
        results = []
        
        for i, step in enumerate(actions):
            action_id = step.get("action")
            params = step.get("parameters", {})
            alias = step.get("alias") # Alias ist optional
            
            # 1. Parameter auflösen (Piping)
            resolved_params, error = PipeResolver.resolve(params, context)
            if error:
                results.append({"step": i, "action": action_id, "status": "error", "message": f"Piping Error: {error}"})
                break
                
            # 2. Ausführen mit intelligenter Fehlerbehandlung
            try:
                res = await self.manager.call_action(action_id, resolved_params)
                
                # Prüfen auf Fehler im Ergebnis (v1 Pattern)
                is_error = False
                if isinstance(res, dict):
                    if res.get("status") == "error" or "error" in res:
                        is_error = True
                
                if is_error:
                    # v1 Genius: Rekonstruiere hilfreichen Fehler aus Metadaten
                    landmark = self.manager.landmarks.get(action_id)
                    if landmark:
                        remedy = res.get("remedy") or landmark.remedy
                        if not remedy:
                            # Automatischen Schema-Hint generieren
                            required_params = [p.name for p in (landmark.parameters or []) if p.required]
                            if required_params:
                                remedy = f"Check your parameters. Required fields: {required_params}. Use 'inspect_landmark(\"{action_id}\")' for details."
                        
                        if remedy:
                            if isinstance(res, dict):
                                res["remedy"] = remedy
                            else:
                                res = {"status": "error", "message": str(res), "remedy": remedy}

                # Ergebnis speichern
                step_res = {"step": i, "action": action_id, "result": res}
                if alias:
                    step_res["alias"] = alias
                    context[alias] = res
                
                # Kontext auch über Index verfügbar machen
                context[str(i)] = res
                results.append(step_res)

                if is_error: break # Abbruch der Sequenz bei Fehler

            except Exception as e:
                results.append({"step": i, "action": action_id, "status": "error", "message": str(e)})
                break
                
        return results
