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

import re
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class SequenceEngine:
    """Verarbeitet Tool-Ketten mit explizitem Piping und Ambiguitäts-Erkennung."""
    
    def __init__(self, manager):
        self.manager = manager

    async def run(self, actions: List[Dict[str, Any]], context: Dict[str, Any], index_offset: int = 0) -> List[Dict[str, Any]]:
        results = []
        for i_raw, action_req in enumerate(actions):
            i = i_raw + index_offset
            step_alias = f"step{i}"
            action_id = action_req.get("action")
            raw_params = action_req.get("parameters", {})
            alias = action_req.get("alias")
            
            # 1. Resolve Condition
            condition = action_req.get("condition")
            if condition:
                resolved_cond, err = self.resolve_all(condition, context)
                if not err:
                    if not self._evaluate_condition(resolved_cond):
                        results.append({
                            "step": i,
                            "action": action_id,
                            "alias": alias,
                            "result": {"status": "skipped", "message": f"Condition '{condition}' not met."}
                        })
                        continue

            # 2. Resolve Piping
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
            context[step_alias] = result
            if alias:
                # Store under custom alias as well
                context[alias] = result

            # Context Hygiene: Omit action if success, keep if error
            res_entry = {
                "step": i,
                "alias": alias or step_alias,
                "result": result
            }
            
            is_error = isinstance(result, dict) and result.get("status") == "error"
            if is_error:
                res_entry["action"] = action_id

            results.append(res_entry)
            
            # 4. Error Handling (on_error: stop|continue)
            on_error = action_req.get("on_error", "stop")
            if is_error and on_error == "stop":
                break
                
        return results

    def resolve_all(self, data: Any, context: Dict[str, Any]) -> Tuple[Any, Optional[str]]:
        """Resolves all placeholders in a nested structure (supports interpolation)."""
        if isinstance(data, str):
            if data.startswith("$") and " " not in data:
                # Direct object reference (could be non-string result)
                return self._resolve_single_value(data, context)
            
            # String interpolation: "Hello $name"
            # We look for $ followed by alphanumeric and optionally [.], stopping at space or end
            def replace_match(match):
                placeholder = match.group(0)
                val, err = self._resolve_single_value(placeholder, context)
                if err: raise ValueError(err)
                return str(val)

            try:
                # This regex finds $alias, $alias.path, $alias[0], $alias[0].path
                # It ensures that a trailing dot (sentence end) is NOT matched.
                new_str = re.sub(r"\$[\w\[\]]+(?:\.[\w\[\]]+)*", replace_match, data)
                return new_str, None
            except ValueError as e:
                return None, str(e)

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
        """Navigiert rekursiv durch Pfade mit Unterstützung für [index]."""
        if not parts:
            return source, None
            
        part = parts[0]
        remaining = parts[1:]

        # Handle indexing in part: "users[1]" -> key="users", index=1
        index_match = re.match(r"(\w+)\[(\d+)\]", part)
        if index_match:
            key, idx_str = index_match.groups()
            idx = int(idx_str)
            
            # First, navigate to the key
            val, err = self._navigate_path(source, [key], alias_context)
            if err: return None, err
            
            # Then, apply index
            if isinstance(val, list):
                if idx < len(val):
                    return self._navigate_path(val[idx], remaining, alias_context)
                return None, f"Index {idx} out of range for '{key}' in '${alias_context}'"
            return None, f"Cannot use index [{idx}] on non-list field '{key}'"

        current_key = part

        if isinstance(source, dict):
            if current_key in source:
                return self._navigate_path(source[current_key], remaining, alias_context)
            
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

    def _evaluate_condition(self, condition: Any) -> bool:
        """Evaluates a boolean condition or expression."""
        if isinstance(condition, bool):
            return condition
        
        if isinstance(condition, str):
            # Simple expression evaluator for Showcase
            # Supports: <, >, ==, !=, is, is not
            try:
                # Remove common AI fluff
                clean = condition.strip().lower()
                if clean in ["true", "yes", "on"]: return True
                if clean in ["false", "no", "off"]: return False
                
                # Comparison support: "22 < 20" or "status == success"
                match = re.match(r"([\w\d\.\-\'\"]+)\s*(<|>|==|!=)\s*([\w\d\.\-\'\"]+)", clean)
                if match:
                    v1, op, v2 = match.groups()
                    # Strip quotes if present
                    v1 = v1.strip("'\"")
                    v2 = v2.strip("'\"")
                    
                    # Try numeric first, then string
                    try:
                        f1, f2 = float(v1), float(v2)
                        if op == "<": return f1 < f2
                        if op == ">": return f1 > f2
                        if op == "==": return f1 == f2
                        if op == "!=": return f1 != f2
                    except ValueError:
                        # Fallback to string comparison
                        if op == "==": return v1 == v2
                        if op == "!=": return v1 != v2
                
                return bool(clean)
            except Exception:
                return False
        return bool(condition)
