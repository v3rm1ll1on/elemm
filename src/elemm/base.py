from typing import List, Dict, Any, Optional, Callable
from .models import AIAction, AIProtocolManifest

DEFAULT_PROTOCOL_INSTRUCTIONS = (
    "You are an autonomous web agent. This manifest defines 'actions' you can call like functions. "
    "DECISION RULES: "
    "1. The 'parameters' field is a SCHEMA. Each key inside is an argument name. "
    "2. NEVER send the schema objects themselves as values. Send only the actual content (e.g., q='Apple'). "
    "3. Optional fields (required: false) are truly optional for you—use them only if they serve the goal. "
    "4. Strictly follow the 'instructions' provided at the action level. "
    "5. CONTEXT HYGIENE: If a tool you need is missing, look for 'navigation' landmarks. They allow you to 'drill-down' into specialized modules with more tools."
)

class BaseAIProtocolManager:
    """
    Framework-agnostic core logic for managing LLM Landmarks.
    """
    def __init__(self, agent_welcome: str, version: str = "v1-lmlmm", protocol_instructions: Optional[str] = None):
        self.version = version
        self.agent_welcome = agent_welcome
        self.protocol_instructions = protocol_instructions or DEFAULT_PROTOCOL_INSTRUCTIONS
        self.actions: List[AIAction] = []
        self.openapi_url: Optional[str] = None

    def landmark(self, id: str, type: str, instructions: Optional[str] = None, description: Optional[str] = None, **kwargs):
        """
        Generic decorator to mark a function as an LLM Landmark.
        This simply attaches metadata to the function object.
        """
        def decorator(func: Callable):
            setattr(func, "_llm_landmark", {
                "id": id,
                "type": type,
                "instructions": instructions,
                "description": description,
                "extra": kwargs
            })
            return func
        return decorator

    def register_action(self, **kwargs):
        """
        Manually register an action in the manifest.
        """
        action = AIAction(**kwargs)
        self.actions.append(action)

    def get_manifest(self, group: Optional[str] = None, agent_view: bool = True) -> Dict[str, Any]:
        """
        Returns the protocol manifest as a dictionary, optionally filtered by group.
        If group is None, returns only entries without specific groups (Entry Points).
        If agent_view is True, filters out 'noise' fields for the LLM.
        """
        filtered_actions = []
        is_internal_group = (group == "_INTERNAL_ALL_")

        for action in self.actions:
            if action.hidden and not is_internal_group:
                continue
            
            # Filter by group logic
            if is_internal_group:
                filtered_actions.append(action)
                continue

            if group:
                if group in action.groups:
                    filtered_actions.append(action)
            else:
                if not action.groups or action.global_access:
                    filtered_actions.append(action)

        # Apply LLM Noise Reduction (if agent_view requested and not internal)
        if agent_view and not is_internal_group:
            # Exclude fields that are technical noise for the LLM
            # We keep 'method' and 'url' because they are essential for technical discovery
            exclude_fields = {
                "groups", "global_access", 
                "tags", "hidden", "headers", "context_dependencies",
                "required_auth"
            }
            
            cleaned_actions = []
            for action in filtered_actions:
                action_dict = action.model_dump(exclude=exclude_fields, exclude_none=True)
                cleaned_actions.append(action_dict)
            
            manifest_data = {
                "version": self.version,
                "agent_welcome": self.agent_welcome,
                "protocol_instructions": self.protocol_instructions,
                "actions": cleaned_actions
            }
            return {k: v for k, v in manifest_data.items() if v is not None}

        manifest = AIProtocolManifest(
            version=self.version,
            agent_welcome=self.agent_welcome,
            protocol_instructions=self.protocol_instructions,
            openapi_url=self.openapi_url,
            actions=filtered_actions
        )
        return manifest.model_dump(exclude_none=True)

    def get_mcp_tools(self, group: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Export registered landmarks as MCP-compatible tool definitions, optionally filtered by group.
        """
        mcp_tools = []
        
        # We reuse the logic from get_manifest but with agent_view=False to get all data
        manifest_data = self.get_manifest(group=group, agent_view=False)
        actions = [AIAction(**a) for a in manifest_data.get("actions", [])]

        for action in actions:
            properties = {}
            required_fields = []

            # Convert ActionParams to JSON Schema properties
            if action.parameters:
                for p in action.parameters:
                    p_type = p.type if p.type in ["string", "number", "integer", "boolean", "array", "object"] else "string"
                    properties[p.name] = {
                        "type": p_type,
                        "description": p.description
                    }
                    if p.required:
                        required_fields.append(p.name)

            # Convert Payload to JSON Schema properties
            if action.payload:
                if isinstance(action.payload, list):
                    # Structured ActionParam List (Preferred)
                    for p in action.payload:
                        p_type = p.type if p.type in ["string", "number", "integer", "boolean", "array", "object"] else "string"
                        properties[p.name] = {
                            "type": p_type,
                            "description": p.description
                        }
                        if p.required:
                            required_fields.append(p.name)
                else:
                    # Legacy Dictionary Support
                    for key, info in action.payload.items():
                        properties[key] = {
                            "type": "string",
                            "description": str(info)
                        }
                        if "[required]" in str(info):
                            required_fields.append(key)

            mcp_tools.append({
                "name": action.id,
                "description": (
                    f"{action.description}\n\n"
                    f"Agent Instructions: {action.instructions or 'Follow API semantics.'}\n"
                    f"Remedy: {action.remedy or 'If error occurs, check parameters and try again.'}"
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": properties,
                    "required": list(set(required_fields))
                }
            })
        
        return mcp_tools
