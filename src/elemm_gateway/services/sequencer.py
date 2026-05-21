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

import json
import asyncio
import time
import logging
from typing import Any, Dict, List
import mcp.types as types
from elemm.core.sequencer import SequenceEngine as CoreSequenceEngine

logger = logging.getLogger("elemm-gateway")

class SequenceEngine(CoreSequenceEngine):
    """Orchestrates multi-step tool calls with data piping and session isolation."""
    def __init__(self, gateway: Any):
        super().__init__(manager=None)
        self.gateway = gateway
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.aliases: Dict[str, Any] = {} # For test backward compatibility

    def get_session_aliases(self, session_id: str) -> Dict[str, Any]:
        if session_id == "default" and self.aliases:
            return self.aliases
        if session_id not in self.sessions:
            self.sessions[session_id] = {}
        return self.sessions[session_id]

    def clear_session(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]
        if self.aliases:
            self.aliases.clear()

    def format_aliases_markdown(self, session_id: str) -> str:
        """Returns a formatted markdown summary of stored findings."""
        aliases = self.get_session_aliases(session_id)
        res = (
            "### SESSION GOVERNANCE\n"
            "- Use 'list_aliases' to see all current session findings ($step0, $step1, etc.).\n"
            "- PIPING: Chain results via '$alias.field' (e.g. '$step0.id') in any parameter.\n"
            "- ISOLATION: Findings are stored for the duration of the 'session_id'.\n"
            "- CLEANUP: Call 'clear_session' after task completion for privacy.\n\n"
        )
        res += f"### MEMORY BANK (Session: {session_id})\n"
        if not aliases:
            res += "- No findings stored yet in this session."
        else:
            for a, v in sorted(aliases.items()):
                # Truncate values for privacy and token economy
                v_str = str(v)
                if len(v_str) > 200: v_str = v_str[:197] + "..."
                res += f"- **${a}**: {v_str}\n"
        return res

    async def execute(self, actions: List[Dict[str, Any]] = None, session_id: str = "default", **kwargs) -> List[types.TextContent]:
        from elemm_gateway.services.monitor import get_monitor
        monitor = get_monitor()
        
        actions = actions or kwargs.get("steps", [])
        if not actions:
            return [types.TextContent(type="text", text="Error: No actions or steps provided in sequence.")]
            
        aliases = self.get_session_aliases(session_id)
        results = []
        raw_results = []
        import time
        sequence_start_time = time.perf_counter()
        
        for i, step in enumerate(actions):
            action_id = step.get("action")
            if not action_id:
                error_res = {"status": "error", "message": "Missing 'action' field in step."}
                results.append({"step": i, "action": None, "alias": step.get("alias") or f"step{i}", "result": error_res})
                continue
                
            norm_action_id = action_id
            if action_id.startswith("elemm-gateway:"):
                norm_action_id = action_id[len("elemm-gateway:"):]
                
            params = step.get("parameters", {})
            # Hygiene params can be sibling to 'parameters' in the action dict
            for hp in ["_select", "_filter", "_limit", "_offset"]:
                if hp in step and hp not in params:
                    params[hp] = step[hp]
            
            alias = step.get("alias")
            on_error = step.get("on_error", "stop")
            
            # Use the robust core resolver (inherits resolve_all)
            resolved_params, err = self.resolve_all(params, aliases)
            if err:
                error_res = {
                    "status": "error",
                    "_PROTOCOL_ERROR": "PIPING_FAILED",
                    "message": f"Data piping failed: {err}",
                    "remedy": "Check if the alias exists and the path is correct using 'elemm:list_aliases'."
                }
                results.append({"step": i, "action": action_id, "alias": alias or f"step{i}", "result": error_res})
                aliases[f"step{i}"] = error_res
                if alias: aliases[alias] = error_res
                if on_error == "stop": break
                continue

            retries = step.get("retry", 0)
            retry_on = step.get("retryOn", [])
            attempt = 0
            
            while attempt <= retries:
                attempt_start = time.perf_counter()
                try:
                    if norm_action_id.startswith("elemm:"):
                        result_val = await self.gateway._execute_single(norm_action_id, resolved_params, session_id=session_id)
                    elif norm_action_id in ["get_manifest", "get_landmarks", "inspect_landmark", "search_landmarks", "list_aliases", "clear_session"]:
                        # Convert 'landmark' to 'landmark_id' for inspect_landmark if they used the alias
                        if norm_action_id == "inspect_landmark" and "landmark" in resolved_params and "landmark_id" not in resolved_params:
                            resolved_params["landmark_id"] = resolved_params["landmark"]
                        tool_results = await self.gateway._proxy_core_tool(norm_action_id, resolved_params, session_id=session_id)
                        result_val = tool_results[0].text
                    else:
                        result_val = await self.gateway._execute_single(norm_action_id, resolved_params, session_id=session_id)
                except Exception as e:
                    result_val = json.dumps({"status": "error", "message": f"Internal Execution Error: {str(e)}"})

                duration_ms = int((time.perf_counter() - attempt_start) * 1000)
                
                try: final_res = json.loads(result_val)
                except: final_res = result_val
                
                if isinstance(final_res, dict) and (final_res.get("status") == "error" or "_PROTOCOL_ERROR" in final_res):
                    proto_err = final_res.get("_PROTOCOL_ERROR")
                    if proto_err in retry_on and attempt < retries:
                        attempt += 1
                        await asyncio.sleep(1)
                        continue
                break

            from elemm_gateway.services.hygiene import ResponseSquisher
            limit = getattr(self.gateway, "limit_standard", 30000)
            
            # Dynamically scale smart limits based on the configured limit_standard
            max_str_len = limit // 2  # E.g. 15,000 chars for a single string block
            max_list_items = max(20, limit // 500) # E.g. 60 items if limit is 30k
            
            # 1. Semantic Squish
            squished_res, was_truncated = ResponseSquisher.smart_truncate(
                final_res, 
                max_list_items=max_list_items, 
                max_string_length=max_str_len
            )
            aliases[f"step{i}"] = squished_res
            if alias: aliases[alias] = squished_res

            # 2. Stringify for final check
            res_str = json.dumps(squished_res, indent=2) if not isinstance(squished_res, str) else squished_res
            
            # 3. Last resort safety cut
            if len(res_str) > limit:
                hint = f"\n\n(Note: Result too large. Truncated to {limit} chars.)"
                res_str = res_str[:limit - len(hint) - 10] + "..." + hint
                was_truncated = True

            results.append({
                "step": i, 
                "action": action_id, 
                "alias": alias or f"step{i}",
                "duration_ms": duration_ms, 
                "result": squished_res,
                "_truncated": was_truncated
            })

            raw_results.append({
                "step": i,
                "action": action_id,
                "alias": alias or f"step{i}",
                "duration_ms": duration_ms,
                "result": final_res, # The raw untruncated result!
                "_truncated": False
            })

            if isinstance(final_res, dict) and (final_res.get("status") == "error" or "_PROTOCOL_ERROR" in final_res) and on_error == "stop":
                break

        # Determine if there's any step error in the sequence
        has_any_error = False
        for r in results:
            res_val = r.get("result")
            if isinstance(res_val, dict) and (res_val.get("status") == "error" or "_PROTOCOL_ERROR" in res_val or res_val.get("status") == "fail"):
                has_any_error = True
                break

        # Broadcast the raw, completely untruncated sequence results to the telemetry layer!
        seq_duration_ms = int((time.perf_counter() - sequence_start_time) * 1000)
        monitor.report_activity(
            last_action=f"RETURN: execute_sequence({len(actions)} steps)",
            input_data={"steps": actions},
            output_data=raw_results,
            status="error" if has_any_error else "success",
            session_id=session_id,
            request_id=kwargs.get("request_id"),
            parent_request_id=kwargs.get("parent_request_id"),
            duration_ms=seq_duration_ms
        )

        # Flag the returned TextContent object to bypass redundant reporting in server.py
        text_res = types.TextContent(type="text", text=json.dumps(results, indent=2))
        setattr(text_res, "_dashboard_reported", True)
        return [text_res]

    def _navigate(self, data: Any, path: str, aliases: Dict[str, Any]) -> Any:
        """Navigates through a data structure using a dot-notated path (for backward compatibility)."""
        if not path:
            return data
        
        # Normalize path: remove leading dot if any
        if path.startswith("."):
            path = path[1:]
        
        parts = []
        # Complex regex to handle both .field and [index]
        import re
        for match in re.finditer(r"([^.\[\]]+)|\[(\d+)\]", path):
            if match.group(1): # field
                parts.append(match.group(1))
            else: # index
                parts.append(int(match.group(2)))
        
        curr = data
        for p in parts:
            if not p: continue
            try:
                if isinstance(p, int):
                    curr = curr[p]
                else:
                    curr = curr[p]
            except (KeyError, IndexError, TypeError):
                available = list(curr.keys()) if isinstance(curr, dict) else "N/A"
                raise ValueError(f"Path component '{p}' failed. Available at this level: {available}")
            
            if curr is None: break
            
        return curr
