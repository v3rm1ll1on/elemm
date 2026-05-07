from typing import Any, Dict, List, Optional
from pydantic import BaseModel

class RepairResult(BaseModel):
    status: str = "error"
    message: str
    remedy: str
    suggested_fix: Optional[str] = None
    example: Optional[str] = None
    expected_schema: Optional[Dict[str, Any]] = None

class SmartRepairEngine:
    """Zentrale Logik für präzise Fehlerbehebung und Agenten-Guiding."""
    
    @staticmethod
    def handle_missing_action(action_id: str, available_ids: List[str]) -> RepairResult:
        import difflib
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
    def handle_invalid_params(action_id: str, missing: List[str], schema: Dict[str, Any]) -> RepairResult:
        example_params = {p: "VALUE" for p in missing}
        return RepairResult(
            message=f"Missing required parameters for '{action_id}': {missing}",
            remedy=f"Provide the missing fields. See technical signature.",
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
            message=f"Direct call to '{tool_id}' is prohibited by protocol.",
            remedy="Use the 'call_action' tool.",
            suggested_fix=example,
            example=example
        )
    
    @staticmethod
    def handle_piping_failure(alias: str, field: str, available_keys: List[str]) -> RepairResult:
        return RepairResult(
            message=f"Piping failed: Field '{field}' not found in alias '{alias}'.",
            remedy=f"Available keys in this alias are: {available_keys}. Use 'list_aliases' to verify state.",
            example=f"${alias}.{available_keys[0]}" if available_keys else None
        )

    @staticmethod
    def handle_namespace_execution_attempt(namespace_id: str) -> RepairResult:
        return RepairResult(
            message=f"Cannot execute '{namespace_id}' because it is a namespace/group, not a specific tool.",
            remedy=f"Call 'inspect_landmarks' with landmark_ids=[\"{namespace_id}\"] to see the available executable tools inside this namespace."
        )
