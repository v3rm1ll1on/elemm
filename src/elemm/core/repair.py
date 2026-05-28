# Copyright (C) 2026 Marc Stöcker
# Website: https://elemm.dev
#
# This program is licensed under the Business Source License 1.1 (BSL 1.1).
# See the LICENSE file in the root directory for details.

from typing import Any, Dict, List, Optional
from pydantic import BaseModel

class RepairResult(BaseModel):
    status: str = "error"
    message: str
    remedy: str
    suggested_fix: Optional[str] = None
    valid_options: Optional[List[str]] = None
    example: Optional[str] = None
    expected_schema: Optional[Dict[str, Any]] = None

class SmartRepairEngine:
    """Zentrale Logik für präzise Fehlerbehebung und Agenten-Guiding."""
    
    @staticmethod
    def normalize_id(s: Any) -> str:
        """Central normalization for IDs and values (lowercase, no symbols)."""
        import re
        return re.sub(r'[^a-z0-9]', '', str(s).lower())

    @staticmethod
    def handle_missing_action(action_id: str, available_ids: List[str]) -> RepairResult:
        import difflib
        
        given_norm = SmartRepairEngine.normalize_id(action_id)
        options_map = {SmartRepairEngine.normalize_id(o): o for o in available_ids}
        
        # 1. Check for normalized match
        if given_norm in options_map:
            best_match = options_map[given_norm]
            return RepairResult(
                message=f"Action '{action_id}' not found.",
                remedy=f"Did you mean '{best_match}'? (Protocol is case-sensitive and uses underscores).",
                suggested_fix=best_match
            )
            
        # 2. Fallback to fuzzy
        suggestions = difflib.get_close_matches(action_id, available_ids, n=3, cutoff=0.5)
        msg = f"Action '{action_id}' not found."
        remedy = f"Please check the manifest. "
        if suggestions:
            remedy += f"Did you mean one of these? {suggestions}"
        
        return RepairResult(
            message=msg,
            remedy=remedy
        )

    @staticmethod
    def handle_invalid_params(action_id: str, missing: List[str], schema: Dict[str, Any], custom_remedy: Optional[str] = None) -> RepairResult:
        example_params = {p: "VALUE" for p in missing}
        remedy = custom_remedy or f"Provide the missing fields. See technical signature."
        
        return RepairResult(
            message=f"Missing required parameters for '{action_id}': {missing}",
            remedy=remedy,
            example=f"call_action(action='{action_id}', parameters={example_params})",
            expected_schema=schema
        )

    @staticmethod
    def handle_prohibited_direct_call(tool_id: str, arguments: Dict[str, Any]) -> RepairResult:
        import json
        # If the agent nested it (e.g., thinking it's inside an execute_sequence block)
        if "parameters" in arguments and "action" in arguments:
            actual_params = arguments["parameters"]
        else:
            actual_params = arguments
            
        example = f"call_action(action='{tool_id}', parameters={json.dumps(actual_params)})"
        return RepairResult(
            message=f"CRITICAL PROTOCOL ERROR: Direct tool execution via MCP is strictly prohibited for '{tool_id}'.",
            remedy="You MUST ALWAYS use the 'call_action' or 'execute_sequence' tools for ALL operations. Never attempt direct calls again.",
            suggested_fix=f"call_action(action='{tool_id}', parameters={json.dumps(actual_params)})",
            example=f"call_action(action='{tool_id}', parameters={json.dumps(actual_params)})"
        )
    
    @staticmethod
    def handle_piping_failure(alias: str, field: str, available_keys: List[str]) -> RepairResult:
        return RepairResult(
            message=f"Piping failed: Field '{field}' not found in alias '{alias}'.",
            remedy=f"Available keys in this alias are: {available_keys}. Use the 'list_aliases' tool to verify current state.",
            example=f"${alias}.{available_keys[0]}" if available_keys else None
        )
    
    @staticmethod
    def handle_remote_error(status_code: int, remote_msg: str) -> RepairResult:
        """Translates HTTP status codes into actionable remedies for the agent."""
        remedy = "Verify technical signatures with 'inspect_landmark' and check your parameters."
        
        if status_code == 404:
            remedy = "The resource was not found. Check if the 'owner', 'repo', or specific IDs (like issue_number) are spelled correctly."
        elif status_code == 401:
            remedy = "Authentication failed. Your ~/.elemm/vault.json might be missing a valid API key for this host."
        elif status_code == 403:
            remedy = "Access denied. This usually means the resource is private or your permissions are insufficient."
        elif status_code == 429:
            remedy = "Rate limit reached. Please wait and reduce the frequency of your calls. Use 'execute_sequence' to batch requests."
        elif status_code == 422:
            remedy = "Validation failed. The parameters were syntactically correct but the remote logic rejected them (e.g. invalid state transition)."
        elif status_code >= 500:
            remedy = "Remote server error. This is a problem on their side. Try again in a few minutes."
            
        msg = f"Remote API Error (HTTP {status_code})"
        if remote_msg:
            msg += f": {remote_msg}"
            
        return RepairResult(
            message=msg,
            remedy=remedy
        )

    @staticmethod
    def handle_namespace_execution_attempt(namespace_id: str) -> RepairResult:
        return RepairResult(
            message=f"STRUCTURAL ERROR: '{namespace_id}' is a Landmark Namespace, not an executable function.",
            remedy=f"You MUST use 'inspect_landmark(landmark_id=\"{namespace_id}\")' to discover the actual tool IDs before execution.",
            example=f"inspect_landmark(landmark_id='{namespace_id}')"
        )

    @staticmethod
    def handle_placeholder_detected(param_name: str, value: Any) -> RepairResult:
        if isinstance(value, str) and value.startswith("$"):
            msg = f"Parameter '{param_name}' contains an unresolved variable: '{value}'."
            remedy = f"The engine could not find a match for '{value}'. Ensure the alias exists or use explicit dot-notation (e.g. $step0.id)."
        else:
            msg = f"Parameter '{param_name}' contains a placeholder value: '{value}'."
            remedy = f"Do not use placeholders like 'UNKNOWN'. You must retrieve the actual value from a previous tool's output first."
            
        return RepairResult(
            message=msg,
            remedy=remedy
        )
    @staticmethod
    def handle_invalid_value(param_name: str, given_value: Any, allowed_options: List[str]) -> RepairResult:
        import difflib
        
        # 1. Exact Case-Insensitive Match
        given_str = str(given_value).lower()
        if given_str in [o.lower() for o in allowed_options]:
            best_match = [o for o in allowed_options if o.lower() == given_str][0]
            return RepairResult(message="Case mismatch fixed.", remedy=f"Used '{best_match}'", suggested_fix=best_match)

        # 2. Normalization Logic
        given_norm = SmartRepairEngine.normalize_id(given_value)
        
        # Find all options that match the normalized input
        matches = [o for o in allowed_options if SmartRepairEngine.normalize_id(o) == given_norm]
        
        if len(matches) == 1:
            best_match = matches[0]
            msg = f"Normalized match found for '{given_value}'."
            return RepairResult(message=msg, remedy=f"Please use the exact ID: '{best_match}'", suggested_fix=best_match)
        elif len(matches) > 1:
            return RepairResult(
                message=f"Ambiguous value '{given_value}' for parameter '{param_name}'.",
                remedy=f"Did you mean one of these? {matches}. Please be more specific."
            )

        # 3. Last Resort: Difflib Fuzzy
        # Map lower to original for retrieval
        lower_to_orig = {o.lower(): o for o in allowed_options}
        suggestions = difflib.get_close_matches(given_str, list(lower_to_orig.keys()), n=3, cutoff=0.5)
        
        msg = f"Invalid value '{given_value}' for parameter '{param_name}'."
        remedy = f"Please use one of the supported values: {allowed_options}."
        
        best_suggestion = lower_to_orig[suggestions[0]] if suggestions else None
        if best_suggestion:
            remedy += f" Did you mean '{best_suggestion}'?"
            
        return RepairResult(
            message=msg,
            remedy=remedy,
            suggested_fix=best_suggestion,
            valid_options=allowed_options
        )

    @staticmethod
    def handle_mcp_error(error_msg: str, tool_data: Optional[Dict[str, Any]] = None) -> RepairResult:
        """Generates a recommendation for MCP tool execution failures using only the configured custom remedy."""
        remedy = ""
        if tool_data:
            custom_remedy = tool_data.get("remedy")
            if custom_remedy:
                remedy = custom_remedy
                
        return RepairResult(
            message=error_msg,
            remedy=remedy
        )