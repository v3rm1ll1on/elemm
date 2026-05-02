import json
import logging
from typing import List, Dict, Any, Optional, Tuple
import mcp.types as types
from ..core.context import landmark_ctx

logger = logging.getLogger("elemm-processor")

class SequenceProcessor:
    """Handles the heavy lifting of sequence execution, parameter resolution, and result formatting."""
    
    def __init__(self, manager, manifest, session_state, pipe_pattern, wrap_pattern):
        self.manager = manager
        self.manifest = manifest
        self.session_state = session_state
        self.PIPE_PATTERN = pipe_pattern
        self.RESULT_WRAP_PATTERN = wrap_pattern

    async def handle_execute_sequence(self, actions: Any) -> List[types.TextContent]:
        # Robustness: Auto-repair stringified JSON arrays
        if isinstance(actions, str):
            try:
                actions = json.loads(actions)
            except:
                pass
        
        if not isinstance(actions, list):
            return [types.TextContent(type="text", text=f"Input validation error: '{actions}' is not of type 'array'.")]

        results = []
        local_results = {} # Maps index (str) OR alias to result
        failed_steps = set()
        
        for i, act in enumerate(actions):
            raw_aid = act.get("action", "") or act.get("action_id", "")
            params = act.get("parameters", {})
            alias = act.get("alias")
            
            aid = raw_aid.strip()
            
            # Strip server prefixes like 'elemm-gateway-list_offices' -> 'list_offices'
            if "-" in aid:
                for prefix in ["elemm-gateway", "gateway", "elemm"]:
                    if aid.startswith(f"{prefix}-"):
                        aid = aid[len(prefix)+1:]
                        break
            # Handle all common separators
            aid = aid.replace("/", ".").replace(":", ".")
            if "." in aid: aid = aid.split(".")[-1].strip()
            
            if self._depends_on_failed(params, failed_steps, local_results):
                results.append(f"Step {i} ({aid}): SKIPPED")
                failed_steps.add(str(i))
                if alias: failed_steps.add(alias)
                continue
            
            if aid in ["inspect_landmark", "get_landmarks"]:
                res_text = self.manifest.generate_summary() if aid == "get_landmarks" else self.manifest.generate_landmark_detail(params.get("landmark_id"))
                res_obj = self._parse_result(res_text)
            else:
                resolved_params, pipe_error = self.resolve_params(params, local_results)
                if pipe_error:
                    results.append(f"Step {i} ({aid}): FAILED. {pipe_error}")
                    failed_steps.add(str(i))
                    if alias: failed_steps.add(alias)
                    continue
                
                res_text = await self.execute_single(aid, resolved_params)
                res_obj = self._parse_result(res_text)
            
            local_results[str(i)] = res_obj
            if alias: local_results[alias] = res_obj
            
            # Outcome handling
            if isinstance(res_obj, dict) and res_obj.get("status") == "error":
                failed_steps.add(str(i))
                if alias: failed_steps.add(alias)
                formatted_res = self.format_result(aid, res_text)
                missing_info = ""
                if "details" in res_obj:
                    details = res_obj["details"]
                    if isinstance(details, list):
                        missing_fields = [d["loc"][-1] for d in details if d.get("type") == "missing"]
                        if missing_fields:
                            missing_info = f" - MISSING FIELDS: {missing_fields}"
                
                results.append(f"Step {i} ({aid}): {formatted_res}{missing_info}")
                results.append(f"\nCRITICAL: Sequence aborted at Step {i}. Use 'call_action' to manually execute the remaining steps.")
                break
            else:
                # SELECTIVE COMPRESSION
                is_boilerplate = isinstance(res_obj, dict) and len(res_obj) == 1 and res_obj.get("status") == "SUCCESS"
                if is_boilerplate and i < len(actions) - 1:
                    results.append(f"Step {i} ({aid}): SUCCESS.")
                else:
                    results.append(f"Step {i}{' (' + alias + ')' if alias else ''} ({aid}): {res_text}")
            
        return [types.TextContent(type="text", text="\n\n".join(results))]

    def _depends_on_failed(self, params: Dict, failed_steps: set, local_results: Dict) -> bool:
        if not params or not failed_steps: return False
        param_str = json.dumps(params)
        placeholders = self.PIPE_PATTERN.findall(param_str)
        for step_key, _, _ in placeholders:
            if step_key in failed_steps: return True
        return False

    def format_result(self, tool_name: str, raw_text: str) -> str:
        try:
            data = json.loads(raw_text)
            if isinstance(data, dict):
                if data.get("status") == "error":
                    msg = data.get("remedy") or data.get("message") or "Unknown error"
                    return f"FAILED. {msg}"
                if len(data) == 1 and "status" in data: return str(data["status"])
                return json.dumps(data)
            return raw_text
        except: return raw_text

    def resolve_params(self, params: Any, local_results: Dict[str, Any]) -> Tuple[Any, Optional[str]]:
        if isinstance(params, str):
            matches = self.PIPE_PATTERN.finditer(params)
            new_val = params
            for m in matches:
                full_match, step_key, index_str, field_name = m.group(0), m.group(1), m.group(2), m.group(3)
                
                if step_key in local_results:
                    data = local_results[step_key]
                elif step_key in self.session_state:
                    data = self.session_state[step_key]
                else:
                    if full_match.startswith("$"):
                        return params, f"PIPE_ERROR: Step or Alias '{step_key}' not found in local or global context. (Hint: Check alias names)."
                    continue
                
                if not full_match.startswith("$"):
                    if step_key.isdigit(): continue
                    if params.strip() != full_match: continue

                if isinstance(data, list):
                    if not data: return params, f"PIPE_ERROR: Step '{step_key}' returned empty list."
                    idx = int(index_str) if index_str is not None else 0
                    if idx >= len(data): return params, f"PIPE_ERROR: Index [{idx}] out of bounds for '{step_key}'."
                    data = data[idx]
                elif index_str is not None:
                    return params, f"PIPE_ERROR: Index [{index_str}] used on non-list at '{step_key}'."
                
                if not isinstance(data, dict) or field_name not in data:
                    avail = ", ".join(data.keys()) if isinstance(data, dict) else "none"
                    return params, f"PIPE_ERROR: Field '{field_name}' not found in '{step_key}'. Available: {avail}"
                
                val = data[field_name]
                if params == full_match or params == f"${{{full_match}}}": return val, None
                
                new_val = new_val.replace(f"${{{full_match.lstrip('$')}}}", str(val))
                new_val = new_val.replace(full_match, str(val))
            return new_val, None
        if isinstance(params, dict):
            new_dict = {}
            for k, v in params.items():
                res, err = self.resolve_params(v, local_results)
                if err: return {}, err
                new_dict[k] = res
            return new_dict, None
        if isinstance(params, list):
            new_list = []
            for item in params:
                res, err = self.resolve_params(item, local_results)
                if err: return [], err
                new_list.append(res)
            return new_list, None
        return params, None

    def _parse_result(self, text: str) -> Any:
        try:
            clean = text.strip()
            if clean.startswith("- "): clean = clean[2:]
            match = self.RESULT_WRAP_PATTERN.search(clean)
            if match: return json.loads(match.group(1))
            return clean
        except: return text

    async def execute_single(self, action_id: str, parameters: Dict) -> str:
        action = self.manager.get_action(action_id)
        if not action:
            if action_id in ["get_manifest", "get_landmarks"]:
                msg = (f"CRITICAL ERROR: '{action_id}' is an MCP Tool, NOT an Action ID! "
                       f"You CANNOT run it inside 'execute_sequence' or 'call_action'. "
                       f"You must invoke '{action_id}' DIRECTLY as a top-level tool call to read the documentation!")
                return json.dumps({"status": "error", "message": msg})
                
            valid_tools = [a.id for a in self.manager.actions]
            msg = f"Tool '{action_id}' DOES NOT EXIST. Stop guessing! Valid tools are: {', '.join(valid_tools)}."
            return json.dumps({"status": "error", "message": msg})
        
        lid = action.groups[0] if action.groups else "root"
        landmark_ctx.set(lid)
        try:
            res, status_code = await self.manager.call_action(action_id, parameters)
            
            if status_code >= 400 or (isinstance(res, dict) and res.get("status") == "error"):
                error_msg = ""
                is_validation_error = False
                
                if status_code == 422 and isinstance(res, dict):
                    detail = res.get("detail") or res.get("details")
                    if detail:
                        if isinstance(detail, list):
                            missing = [e.get("loc", ["?"])[-1] for e in detail if e.get("type") == "missing"]
                            if missing:
                                error_msg = f"Missing required parameters: {', '.join(missing)}."
                                is_validation_error = True
                        else:
                            error_msg = str(detail)
                
                if not error_msg:
                    if isinstance(res, dict):
                        error_msg = res.get("error") or res.get("detail") or res.get("message") or "Validation Failed"
                    else:
                        error_msg = str(res)
                        
                error_msg = str(error_msg).replace("422: Unprocessable Entity", "Validation Error")
                
                if isinstance(res, dict) and "noise_warning" in res:
                    error_msg += f" {res['noise_warning']}"
                    is_validation_error = True
                
                if not is_validation_error:
                    remedy = (res.get("remedy") if isinstance(res, dict) else None) or action.remedy
                    if remedy:
                        error_msg = f"{error_msg}. REMEDY: {remedy}"
                else:
                    error_msg += " DO NOT GIVE UP. You made a syntax typo in the parameter names."
                    seen_params = {}
                    all_params = (getattr(action, "parameters", []) or [])
                    if isinstance(getattr(action, "payload", None), list):
                        all_params += action.payload
                    for p in all_params:
                        if p.name not in seen_params or getattr(p, 'required', False):
                            seen_params[p.name] = p
                    unique_params = list(seen_params.values())
                    if unique_params:
                        schema_hint = " {" + ", ".join(f"'{p.name}': '{p.type}'" for p in unique_params if getattr(p, 'required', True)) + "}"
                        error_msg += f" The required parameters for this tool are: {schema_hint}."
                    error_msg += " Please CALL THE TOOL AGAIN using the exact parameter names from the manifest!"
                    
                return json.dumps({"status": "error", "message": error_msg})

            return json.dumps(res) if isinstance(res, (dict, list)) else str(res)
        except Exception as e: 
            logger.exception(f"Action execution failed: {e}")
            return json.dumps({"status": "error", "message": f"Error: {str(e)}"})
