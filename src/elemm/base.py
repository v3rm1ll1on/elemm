from typing import List, Dict, Any, Optional, Callable
from .models import AIAction, AIProtocolManifest
from .exceptions import LandmarkRegistrationError, ManifestGenerationError, LandmarkNotFoundError
import logging

logger = logging.getLogger(__name__)

DEFAULT_PROTOCOL_INSTRUCTIONS = (
    "You are an autonomous agent using 'Landmarks' to navigate this API. "
    "DECISION RULES: "
    "1. The 'parameters' and 'payload' fields define the tool interface. "
    "2. Landmarks of type 'navigation' open new modules. "
    "3. Landmarks of type 'read'/'write' are functional tools. "
    "4. AUTHENTICATION: This protocol automatically manages sensitive headers (e.g. Auth, API Keys). "
    "Do NOT attempt to manually provide credentials if they are 'managed_by: protocol'. Focus only on business parameters. "
    "5. CONTEXT HYGIENE: If a tool is missing, use 'navigation' to explore more specialized modules."
)

class BaseAIProtocolManager:
    """
    Framework-agnostic core logic for managing LLM Landmarks.
    """
    def __init__(self, agent_welcome: str, version: str = "v1-lmlmm", protocol_instructions: Optional[str] = None, internal_access_key: Optional[str] = None):
        self.version = version
        self.agent_welcome = agent_welcome
        self.protocol_instructions = protocol_instructions or DEFAULT_PROTOCOL_INSTRUCTIONS
        self.actions: List[AIAction] = []
        self._registered_ids = set()
        self.openapi_url: Optional[str] = None
        self.internal_access_key = internal_access_key

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

    # Aliases for better developer experience
    def tool(self, **kwargs):
        """Alias for landmark(type='read')"""
        kwargs.setdefault("type", "read")
        return self.landmark(**kwargs)
    
    def action(self, **kwargs):
        """Alias for landmark(type='write')"""
        kwargs.setdefault("type", "write")
        return self.landmark(**kwargs)

    def register_action(self, **kwargs):
        """
        Manually register an action in the manifest.
        """
        action_id = kwargs.get("id")
        if action_id in self._registered_ids:
            logger.warning(f"Landmark ID '{action_id}' is already registered. Overwriting.")
            # We remove the old one if we want to overwrite, or we could just append. 
            # Protocol-wise, ID must be unique. Let's filter out the old one.
            self.actions = [a for a in self.actions if a.id != action_id]
        
        action = AIAction(**kwargs)
        self.actions.append(action)
        if action_id:
            self._registered_ids.add(action_id)

    def get_manifest(self, group: Optional[str] = None, agent_view: bool = True, read_only: bool = False, internal_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Returns the protocol manifest as a dictionary, optionally filtered by group.
        If group is None, returns only entries without specific groups (Entry Points).
        If agent_view is True, filters out 'noise' fields for the LLM.
        If read_only is True, filters out 'write' actions.
        """
        filtered_actions = []
        is_internal_group = (group == "_INTERNAL_ALL_")

        if is_internal_group:
            # Security Check: Only allow _INTERNAL_ALL_ if configured and key matches
            if not self.internal_access_key:
                raise LandmarkNotFoundError("Internal access is not configured.")
            
            if internal_key != self.internal_access_key:
                # We use LandmarkNotFoundError to avoid leaking existence of the endpoint to unauthorized users
                raise LandmarkNotFoundError("Invalid internal access key.")

        for action in self.actions:
            if action.hidden and not is_internal_group:
                continue
            
            # Read-only filtering (Security Feature)
            if read_only and not is_internal_group:
                is_write = (action.type == "write") or \
                           (action.method and action.method.upper() in ["POST", "PUT", "DELETE", "PATCH"])
                if is_write:
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

    def get_mcp_tools(self, group: Optional[str] = None, internal_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Export registered landmarks as MCP-compatible tool definitions, optionally filtered by group.
        """
        mcp_tools = []
        
        # We reuse the logic from get_manifest but with agent_view=False to get all data
        manifest_data = self.get_manifest(group=group, agent_view=False, internal_key=internal_key)
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
