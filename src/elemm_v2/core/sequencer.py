import re
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class SequenceEngine:
    """Verarbeitet Tool-Ketten mit explizitem Piping und Ambiguitäts-Erkennung."""
    
    def __init__(self, manager):
        self.manager = manager

    async def run(self, actions: List[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        results = []
        for i, action_req in enumerate(actions):
            action_id = action_req.get("action")
            raw_params = action_req.get("parameters", {})
            alias = action_req.get("alias")
            
            # 1. Resolve Piping
            resolved_params, err = self.resolve_all(raw_params, context)
            if err:
                results.append({
                    "step": i,
                    "action": action_id,
                    "alias": alias or step_alias,
                    "result": {
                        "status": "error",
                        "message": f"Piping failed: {err}",
                        "remedy": "Ensure the field exists or use explicit indexing (e.g. $step0[0].id) if the source is a list."
                    }
                })
                break

            # 2. Execute via Manager
            result = await self.manager.call_action(action_id, resolved_params)
            
            # 3. Store results
            step_alias = f"step{i}"
            context[step_alias] = result
            if alias:
                context[alias] = result

            # Context Hygiene: Omit action if success, keep if error
            res_entry = {
                "step": i,
                "alias": alias or step_alias,
                "result": result
            }
            if isinstance(result, dict) and result.get("status") == "error":
                res_entry["action"] = action_id

            results.append(res_entry)
            
            if isinstance(result, dict) and result.get("status") == "error":
                break
                
        return results

    def resolve_all(self, data: Any, context: Dict[str, Any]) -> Tuple[Any, Optional[str]]:
        """Resolves all placeholders in a nested structure."""
        if isinstance(data, str) and data.startswith("$"):
            return self._resolve_single_value(data, context)

        if isinstance(data, dict):
            new_dict = {}
            for k, v in data.items():
                res, err = self.resolve_all(v, context)
                if err: return None, err
                new_dict[k] = res
            return new_dict, None

        if isinstance(data, list):
            new_list = []
            for item in data:
                res, err = self.resolve_all(item, context)
                if err: return None, err
                new_list.append(res)
            return new_list, None

        return data, None

    def _resolve_single_value(self, placeholder: str, context: Dict[str, Any]) -> Tuple[Any, Optional[str]]:
        """Löst einen einzelnen Platzhalter auf ($alias[index].field.path)."""
        # Regex für komplexe Pfade: $alias[index].rest.of.path
        match = re.match(r"\$(\w+)(?:\[(\d+)\])?(?:\.(.*))?", placeholder)
        if not match:
            return placeholder, None

        alias_name, index, path = match.groups()
        
        if alias_name not in context:
            return placeholder, None # Keep literal if alias unknown

        source = context[alias_name]
        
        # 1. Handle Indexing
        if index is not None:
            idx = int(index)
            if isinstance(source, list):
                if idx < len(source):
                    source = source[idx]
                else:
                    return None, f"Index {idx} out of range for '${alias_name}' (size: {len(source)})"
            else:
                return None, f"Cannot use index [{idx}] on non-list object '${alias_name}'"

        # 2. Handle Path Navigation
        if not path:
            return source, None

        return self._navigate_path(source, path.split("."), alias_name)

    def _navigate_path(self, source: Any, parts: List[str], alias_context: str) -> Tuple[Any, Optional[str]]:
        """Navigiert rekursiv durch Pfade mit Ambiguitäts-Erkennung."""
        if not parts:
            return source, None
            
        current_key = parts[0]
        remaining = parts[1:]

        if isinstance(source, dict):
            if current_key in source:
                return self._navigate_path(source[current_key], remaining, alias_context)
            
            # Single-field unwrap (fallback)
            if len(source) == 1 and not remaining:
                return list(source.values())[0], None
                
            return None, f"Field '{current_key}' not found in '${alias_context}'. Available: {list(source.keys())}"

        if isinstance(source, list):
            # List navigation: Try to find the key in list items
            matches = []
            for item in source:
                val, err = self._navigate_path(item, [current_key], alias_context)
                if err is None and val is not None:
                    if val not in matches: matches.append(val)
            
            if len(matches) == 1:
                # One unique match found, continue navigation if needed
                return self._navigate_path(matches[0], remaining, alias_context)
            
            if len(matches) > 1:
                return None, f"Ambiguity in '${alias_context}': Field '{current_key}' has multiple values {matches}. Use explicit index (e.g. ${alias_context}[0].{current_key})."
            
            if not matches:
                # Help the agent: Show what's inside the first item to explain the structure
                if source and isinstance(source[0], dict):
                    keys = list(source[0].keys())
                    return None, f"Field '{current_key}' not found in any item of list '${alias_context}'. Available in items: {keys}"
                return None, f"Field '{current_key}' not found in any item of list '${alias_context}'."

        return None, f"Cannot navigate to '{current_key}' on primitive type {type(source).__name__}"
