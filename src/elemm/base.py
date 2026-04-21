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

class AIProtocolManager:
    """
    Framework-agnostic core logic for managing LLM Landmarks.
    """
    def __init__(self, agent_welcome: str, version: str = "v1-lmlmm", protocol_instructions: Optional[str] = None, internal_access_key: Optional[str] = None, hybrid_threshold: int = 10):
        self.version = version
        self.agent_welcome = agent_welcome
        self.protocol_instructions = protocol_instructions or DEFAULT_PROTOCOL_INSTRUCTIONS
        self.actions: List[AIAction] = []
        self._registered_ids = set()
        self.openapi_url: Optional[str] = None
        self.internal_access_key = internal_access_key
        self.hybrid_threshold = hybrid_threshold

    async def call_action(self, action_id: str, arguments: Dict[str, Any]) -> Any:
        """
        To be implemented by framework-specific managers.
        """
        raise NotImplementedError("This method must be implemented by a subclass.")

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
        Returns the protocol manifest as a dictionary.
        Separates navigation from actions for token efficiency.
        """
        navigation = []
        actions = []
        
        is_internal_group = (group == "_INTERNAL_ALL_")
        is_authorized = (self.internal_access_key and internal_key == self.internal_access_key)

        # Hybrid Mode: Auto-Flattening
        # If fewer than 10 landmarks AND no groups are defined, we skip the group filter
        # to reduce the 'Navigation Tax' for very simple, flat APIs.
        has_groups = any(a.groups for a in self.actions if a.type != "navigation")
        if not group and (len(self.actions) < self.hybrid_threshold and not has_groups):
            # If we are at root and the API is small AND flat, we act as 'INTERNAL_ALL' (unfiltered) 
            # for functional tools.
            is_internal_group = True
        
        for action in self.actions:
            if action.hidden and not is_authorized:
                continue
            
            # Read-only filtering
            if read_only and not is_internal_group:
                is_write = (action.type == "write") or \
                           (action.method and action.method.upper() in ["POST", "PUT", "DELETE", "PATCH"])
                if is_write:
                    continue

            # Filter by group logic
            current_query_group = group or "root"
            in_group = (current_query_group in action.groups) or (not action.groups and current_query_group == "root")
            
            if not in_group and not action.global_access and not is_internal_group and not is_authorized:
                continue

            # Separate Navigation from Actions
            if action.type == "navigation":
                nav_entry = {
                    "id": action.id,
                    "description": action.description
                }
                if action.instructions:
                    nav_entry["instructions"] = action.instructions
                
                navigation.append(nav_entry)
                continue

            # LLM Noise Reduction: Hide tools tagged with 'noise' in agent_view
            if agent_view and not is_internal_group:
                if action.tags and "noise" in [t.lower() for t in action.tags]:
                    continue

            # Clean Action for LLM
            if agent_view and not is_internal_group:
                exclude_fields = {"groups", "global_access", "tags", "hidden", "headers", "context_dependencies", "required_auth"}
                action_dict = action.model_dump(exclude=exclude_fields, exclude_none=True)
                actions.append(action_dict)
            else:
                actions.append(action.model_dump(exclude_none=True))

        return {
            "version": "v1-lmlmm",
            "agent_welcome": self.agent_welcome,
            "protocol_instructions": self.protocol_instructions,
            "current_group": group or "root",
            "navigation": navigation,
            "actions": actions
        }

    def get_mcp_tools(self, group: Optional[str] = None, internal_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Export registered landmarks as MCP-compatible tool definitions, optionally filtered by group.
        """
        mcp_tools = []
        
        # We reuse the logic from get_manifest with agent_view=True 
        # This allows us to exclude 'noise' or 'hidden' tools from the MCP list
        manifest_data = self.get_manifest(group=group, agent_view=True, internal_key=internal_key)
        actions = [AIAction(**a) for a in manifest_data.get("actions", [])]

        for action in actions:
            properties = {}
            required_fields = []

            # Convert ActionParams to JSON Schema properties
            if action.parameters:
                for p in action.parameters:
                    if p.name == "req": continue
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
                        if p.name == "req": continue
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
                        if key == "req": continue
                        properties[key] = {
                            "type": "string",
                            "description": str(info)
                        }
                        if "[required]" in str(info):
                            required_fields.append(key)

            # Compact description with Module Prefix for orientation
            # Remedy and Instructions are now injected on 4xx errors via the Agent Repair Kit
            ctx_label = f"[Module: {group or 'root'}] "
            desc_parts = [f"{ctx_label}TOOL: {action.description}"]
            
            mcp_tools.append({
                "name": action.id,
                "description": "\n".join(desc_parts),
                "inputSchema": {
                    "type": "object",
                    "properties": properties,
                    "required": list(set(required_fields))
                }
            })
        
        return mcp_tools
