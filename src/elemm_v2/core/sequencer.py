import re
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class SequenceEngine:
    """Verarbeitet Tool-Ketten mit dynamischem Deep-Piping und Semantic Unboxing."""
    
    def __init__(self, manager):
        self.manager = manager

    async def run(self, actions: List[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        results = []
        for i, action_req in enumerate(actions):
            action_id = action_req.get("action")
            raw_params = action_req.get("parameters", {})
            alias = action_req.get("alias")
            
            # 1. Resolve Piping
            resolved_params, err = self._resolve_piping(raw_params, context, action_id=action_id)
            if err:
                results.append({
                    "step": i,
                    "action": action_id,
                    "result": f"ERROR: Piping failed. {err}",
                    "alias": alias
                })
                break

            # 2. Execute via Manager
            result = await self.manager.call_action(action_id, resolved_params)
            
            # 3. Store results for future piping
            step_alias = f"step_{i}"
            context[step_alias] = result
            if alias:
                context[alias] = result

            results.append({
                "step": i,
                "action": action_id,
                "result": result,
                "alias": alias or step_alias
            })
            
            # Stop on errors
            if isinstance(result, dict) and result.get("status") == "error":
                break
                
        return results

    def _resolve_piping(self, data: Any, context: Dict[str, Any], action_id: Optional[str] = None) -> Tuple[Any, Optional[str]]:
        """Resolves piped variables like $alias or $alias.field.path"""
        if isinstance(data, str) and data.startswith("$"):
            var_name = data[1:]
            
            # 1. Exact match (handles aliases with dots like 'step0.hostname')
            if var_name in context:
                return context[var_name], None
            
            # 2. Deep path resolution (e.g. $node_info.result.hostname)
            parts = var_name.split(".")
            alias = parts[0]
            
            if alias not in context:
                return data, None # Keep literal if not a known variable
            
            source = context[alias]
            
            # Navigate path
            for part in parts[1:]:
                if isinstance(source, dict) and part in source:
                    source = source[part]
                elif isinstance(source, list) and part.isdigit():
                    idx = int(part)
                    if idx < len(source): source = source[idx]
                    else: return None, f"Index {idx} out of range for '{alias}'"
                else:
                    # Semantic Fallback: Try matching 'part' inside 'source' (even if list/dict)
                    match = self._find_semantic_match(source, part)
                    if match is not None:
                        source = match
                    else:
                        break # Path broken
            
            return source, None

        if isinstance(data, dict):
            new_dict = {}
            for k, v in data.items():
                resolved, err = self._resolve_piping(v, context, action_id=action_id)
                if err: return None, err
                
                # Semantic Unboxing: Find field 'k' inside 'resolved'
                if isinstance(resolved, (dict, list)):
                    match = self._find_semantic_match(resolved, k)
                    if match is not None:
                        resolved = match
                
                new_dict[k] = resolved
            return new_dict, None

        if isinstance(data, list):
            res_list = []
            for item in data:
                res, err = self._resolve_piping(item, context, action_id=action_id)
                if err: return None, err
                res_list.append(res)
            return res_list, None

        return data, None

    def _find_semantic_match(self, obj: Any, target_key: str) -> Any:
        """Looks for a match for target_key inside obj (dict or list)."""
        if isinstance(obj, dict):
            # 1. Exact Match
            if target_key in obj:
                return obj[target_key]
            
            # 2. Common technical synonyms (Heuristic)
            synonyms = {
                "hostname": ["node_id", "srv_name", "host", "node"],
                "token": ["evidence_token", "rt_token", "id"],
                "account_id": ["account_ref", "acc_no", "account"],
                "username": ["principal", "user", "uid"]
            }
            for syn in synonyms.get(target_key, []):
                if syn in obj: return obj[syn]
            
            # 3. Single-field Unwrap
            if len(obj) == 1:
                return list(obj.values())[0]
                
        elif isinstance(obj, list):
            # Search inside list elements
            candidates = []
            for item in obj:
                match = self._find_semantic_match(item, target_key)
                if match is not None:
                    candidates.append(match)
            
            # Ambiguity Handling: If we find multiple candidates, don't guess!
            if len(candidates) > 1:
                logger.warning(f"Ambiguity detected for '{target_key}': {candidates}")
                return None
                
            if len(candidates) == 1:
                return candidates[0]
        
        return None
