from typing import List, Dict, Any, Optional, Callable
from .models import AIAction, AIProtocolManifest

class BaseAIProtocolManager:
    """
    Framework-agnostic core logic for managing LLM Landmarks.
    """
    def __init__(self, agent_welcome: str, version: str = "v1-lmlmm"):
        self.version = version
        self.agent_welcome = agent_welcome
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
        Useful for non-automatic frameworks or special cases.
        """
        if kwargs.get("hidden"):
            return
        action = AIAction(**kwargs)
        self.actions.append(action)

    def get_manifest(self) -> Dict[str, Any]:
        """
        Returns the full protocol manifest as a dictionary.
        """
        manifest = AIProtocolManifest(
            version=self.version,
            agent_welcome=self.agent_welcome,
            openapi_url=self.openapi_url,
            actions=self.actions
        )
        return manifest.model_dump(exclude_none=True)

    def get_mcp_tools(self) -> List[Dict[str, Any]]:
        """
        Export all registered landmarks as MCP-compatible tool definitions.
        Useful for integrating with Claude Desktop, Cursor, and other MCP clients.
        """
        mcp_tools = []
        for action in self.actions:
            # Check if it's hidden or not eligible for MCP
            if action.hidden:
                continue

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
                "description": f"{action.description}\n\nAgent Instructions: {action.instructions or 'Follow API semantics.'}",
                "inputSchema": {
                    "type": "object",
                    "properties": properties,
                    "required": list(set(required_fields))
                }
            })
        
        return mcp_tools
