from typing import List, Dict, Any, Optional, Callable
from .models import AIAction, AIProtocolManifest
from .exceptions import LandmarkRegistrationError, ManifestGenerationError, LandmarkNotFoundError
import logging

logger = logging.getLogger(__name__)

DEFAULT_PROTOCOL_INSTRUCTIONS = (
    "ELEMM PROTOCOL: Navigate via 'get_manifest' and 'navigate'. "
    "Once inside a landmark, all its specific tools are available directly in your toolbelt. "
    "Call them natively (e.g., query_logs()) instead of using a generic executor."
)

class BaseAIProtocolManager:
    """
    Framework-agnostic core logic for managing LLM Landmarks.
    """
    def __init__(self, agent_welcome: Optional[str] = None, version: str = "v1-lmlmm", protocol_instructions: Optional[str] = None, internal_access_key: Optional[str] = None, hybrid_threshold: int = 10, agent_instructions: Optional[str] = None, navigation_landmarks: Optional[List[Dict[str, Any]]] = None):
        self.version = version
        self.agent_welcome = agent_welcome
        self.agent_instructions = agent_instructions
        self.protocol_instructions = protocol_instructions or DEFAULT_PROTOCOL_INSTRUCTIONS
        self.actions: List[AIAction] = []
        self._registered_ids = set()
        self.openapi_url: Optional[str] = None
        self.internal_access_key = internal_access_key
        self.hybrid_threshold = hybrid_threshold
        self.navigation_landmarks = navigation_landmarks or []

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
        def decorator(func):
            if "id" not in kwargs:
                kwargs["id"] = func.__name__
            kwargs.setdefault("type", "read")
            self.register_action(func, **kwargs)
            return func
        return decorator
    
    def action(self, **kwargs):
        def decorator(func):
            if "id" not in kwargs:
                kwargs["id"] = func.__name__
            kwargs.setdefault("type", "write")
            self.register_action(func, **kwargs)
            return func
        return decorator

    def register_action(self, handler: Optional[Callable] = None, **kwargs):
        """
        Manually register an action in the manifest.
        """
        action_id = kwargs.get("id")
        if action_id in self._registered_ids:
            logger.debug(f"Landmark ID '{action_id}' is being updated with new metadata.")
            self.actions = [a for a in self.actions if a.id != action_id]
        
        # LLM Metadata Hierarchy: instructions > description > docstring
        doc = handler.__doc__.strip() if handler and handler.__doc__ else None
        
        # We prioritize 'instructions' as the primary LLM guidance if provided
        final_description = kwargs.get("instructions") or kwargs.get("description") or doc or f"Action: {action_id}"
        kwargs["description"] = final_description

        action = AIAction(handler=handler, **kwargs)
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
        current_query_group = group or "root"
        is_internal_auth = self._check_internal_auth(group, internal_key)
        
        navigation = self._get_navigation_entries(current_query_group)
        actions = []
        
        # Flattening logic: Show all if few actions and no grouping
        is_flattened = False
        has_groups = any(a.groups for a in self.actions if a.type != "navigation")
        if not group and (len(self.actions) < self.hybrid_threshold and not has_groups):
            is_flattened = True
        
        for action in self.actions:
            if not self._should_include_action(action, current_query_group, is_internal_auth, read_only, is_flattened, agent_view):
                continue
            
            if action.type == "navigation":
                navigation.append(self._format_navigation_entry(action, agent_view, is_internal_auth))
            else:
                actions.append(self._format_action_for_manifest(action, agent_view, is_internal_auth))

        return {
            "version": self.version,
            "agent_welcome": self.agent_welcome,
            "protocol_instructions": self.protocol_instructions,
            "current_group": current_query_group,
            "navigation": navigation,
            "actions": actions
        }

    def _check_internal_auth(self, group: Optional[str], internal_key: Optional[str]) -> bool:
        if group != "_INTERNAL_ALL_":
            return False
            
        if not self.internal_access_key:
            raise LandmarkNotFoundError("Internal access is not configured.")
            
        if internal_key != self.internal_access_key:
            raise LandmarkNotFoundError("Invalid internal access key.")
            
        return True

    def _get_navigation_entries(self, group: str) -> List[Dict[str, Any]]:
        if group != "root":
            return []
            
        if self.navigation_landmarks:
            return list(self.navigation_landmarks)
            
        # Auto-generate navigation from action groups
        nav = []
        groups = set()
        for action in self.actions:
            for g in action.groups:
                if g != "root":
                    groups.add(g)
        for g in sorted(list(groups)):
            nav.append({"id": g, "type": "navigation", "description": f"Navigate to {g}"})
        return nav

    def _should_include_action(self, action, group: str, is_internal: bool, read_only: bool, is_flattened: bool, agent_view: bool) -> bool:
        if action.hidden and not is_internal:
            return False
            
        # Read-only filtering
        if read_only and not is_internal:
            is_write = (action.type == "write") or \
                       (action.method and action.method.upper() in ["POST", "PUT", "DELETE", "PATCH"])
            if is_write:
                return False

        # Group filtering
        in_group = (group in action.groups) or (not action.groups and group == "root")
        if not in_group and not action.global_access and not is_internal and not is_flattened:
            return False

        # Noise reduction
        if agent_view and not is_internal:
            if action.tags and "noise" in [t.lower() for t in action.tags]:
                return False
                
        return True

    def _format_navigation_entry(self, action, agent_view: bool, is_internal: bool) -> Dict[str, Any]:
        nav_entry = {
            "id": action.id,
            "description": action.description,
            "type": "navigation"
        }
        if action.instructions:
            nav_entry["instructions"] = action.instructions
        
        if not agent_view or is_internal:
            nav_entry["url"] = action.url
            nav_entry["opens_group"] = action.opens_group
        return nav_entry

    def _format_action_for_manifest(self, action, agent_view: bool, is_internal: bool) -> Dict[str, Any]:
        if agent_view and not is_internal:
            exclude_fields = {"groups", "global_access", "tags", "hidden", "headers", "context_dependencies", "required_auth"}
            return action.model_dump(exclude=exclude_fields, exclude_none=True)
        return action.model_dump(exclude_none=True)
