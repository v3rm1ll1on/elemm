# This file is part of Elemm.
#
# Elemm is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Elemm is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Elemm.  If not, see <https://www.gnu.org/licenses/>.

from typing import List, Dict, Any, Optional, Callable
from .models import AIAction, AIProtocolManifest
from .exceptions import LandmarkRegistrationError, ManifestGenerationError, LandmarkNotFoundError, ActionError
import logging

logger = logging.getLogger(__name__)

DEFAULT_PROTOCOL_INSTRUCTIONS = "ELEMM: [MNFST -> NAV -> EXEC]. Use 'execute_sequence' for BATCHING (multiple tools in one turn) and PIPING (chain results via $N.field or $N[index].field)."

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

    @property
    def landmarks(self) -> List[Dict[str, Any]]:
        """Returns all registered landmarks for discovery."""
        return self._get_navigation_entries("root")

    async def call_action(self, action_id: str, arguments: Dict[str, Any]) -> tuple[Any, int]:
        """
        Direct execution of a registered Python function.
        Returns (result, status_code) to remain compatible with MCP bridge expectations.
        """
        action = next((a for a in self.actions if a.id == action_id), None)
        if not action:
            raise ValueError(f"Action {action_id} not found.")
            
        if not action.handler:
            raise ValueError(f"Action {action_id} has no registered handler.")
            
        import inspect
        try:
            if inspect.iscoroutinefunction(action.handler):
                result = await action.handler(**arguments)
            else:
                result = action.handler(**arguments)
            return result, 200
        except ActionError as e:
            logger.error(f"Action {action_id} failed: {e.message}")
            res = {"error": e.message, "status": "error"}
            if e.remedy: res["remedy"] = e.remedy
            if e.instruction: res["instruction"] = e.instruction
            return res, e.status_code
        except Exception as e:
            return {"error": str(e), "status": "error"}, 500

    def get_action(self, action_id: str) -> Optional[AIAction]:
        """Returns a registered action by its ID."""
        return next((a for a in self.actions if a.id == action_id), None)

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
            
            # Attach metadata for discovery
            meta = {
                "id": kwargs["id"],
                "type": kwargs["type"],
                "instructions": kwargs.get("instructions"),
                "description": kwargs.get("description"),
                "extra": {k: v for k, v in kwargs.items() if k not in ["id", "type", "instructions", "description", "remedy"]}
            }
            # Put remedy in extra if exists
            if "remedy" in kwargs:
                meta["extra"]["remedy"] = kwargs["remedy"]
                
            setattr(func, "_llm_landmark", meta)
            
            self.register_action(func, **kwargs)
            return func
        return decorator
    
    def action(self, **kwargs):
        def decorator(func):
            if "id" not in kwargs:
                kwargs["id"] = func.__name__
            kwargs.setdefault("type", "write")
            
            # Attach metadata for discovery
            meta = {
                "id": kwargs["id"],
                "type": kwargs["type"],
                "instructions": kwargs.get("instructions"),
                "description": kwargs.get("description"),
                "extra": {k: v for k, v in kwargs.items() if k not in ["id", "type", "instructions", "description", "remedy"]}
            }
            # Put remedy in extra if exists
            if "remedy" in kwargs:
                meta["extra"]["remedy"] = kwargs["remedy"]
                
            setattr(func, "_llm_landmark", meta)
            
            self.register_action(func, **kwargs)
            return func
        return decorator

    def returns(self, fields: Dict[str, str]):
        """
        Decorator to document return fields for an action.
        Example: @ai.returns({"token": "The evidence token (RT-XXXX)"})
        """
        def decorator(func: Callable):
            existing = getattr(func, "_llm_returns", {})
            existing.update(fields)
            setattr(func, "_llm_returns", existing)
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
        
        # Infer output schema from return type hint if available (Pydantic Magic)
        response_schema = kwargs.get("response_schema")
        if not response_schema and handler:
            # Infer output schema from return type hint if available
            from typing import get_type_hints, get_origin, get_args
            try:
                hints = get_type_hints(handler)
                return_hint = hints.get('return')
                if return_hint:
                    # 1. Pydantic Models
                    if hasattr(return_hint, "model_json_schema"):
                        response_schema = return_hint.model_json_schema()
                    elif hasattr(return_hint, "__pydantic_model__"):
                        response_schema = return_hint.__pydantic_model__.model_json_schema()
                    # 2. Lists (Generic Aliases)
                    elif get_origin(return_hint) is list:
                        inner = get_args(return_hint)[0]
                        inner_schema = {"type": "string"}
                        if hasattr(inner, "model_json_schema"):
                            inner_schema = inner.model_json_schema()
                        elif inner is dict:
                            inner_schema = {"type": "object"}
                        response_schema = {"type": "array", "items": inner_schema}
                    # 3. Simple types
                    elif return_hint is list:
                        response_schema = {"type": "array", "items": {"type": "object"}}
                    elif return_hint is dict:
                        response_schema = {"type": "object"}
                    elif return_hint is str:
                        response_schema = {"type": "string"}
            except Exception as e:
                logger.debug(f"Could not infer output schema: {e}")
        
        # Manual 'returns' override/supplement
        returns = kwargs.get("returns") or (getattr(handler, "_llm_returns", None) if handler else None)
        if returns and not response_schema:
            if isinstance(returns, list):
                response_schema = {"type": "object", "properties": {k: {"type": "string"} for k in returns}}
            elif isinstance(returns, dict):
                response_schema = {"type": "object", "properties": {k: {"type": "string", "description": v} for k, v in returns.items()}}
        
        # If schema exists but we have documented returns, merge descriptions
        if response_schema and isinstance(returns, dict):
            props = response_schema.get("properties", {})
            if response_schema.get("type") == "array":
                props = response_schema.get("items", {}).get("properties", {})
            
            for k, v in returns.items():
                if k in props:
                    props[k]["description"] = v
        
        # We prioritize 'instructions' as the primary LLM guidance if provided
        final_description = kwargs.get("instructions") or kwargs.get("description") or doc or f"Action: {action_id}"
        kwargs["description"] = final_description
        kwargs["response_schema"] = response_schema

        if "parameters" not in kwargs and handler:
            import inspect
            from .discovery import map_type
            from .models import ActionParam
            sig = inspect.signature(handler)
            parameters = []
            for name, param in sig.parameters.items():
                p_type, p_options = map_type(param.annotation)
                p_required = param.default == inspect.Parameter.empty
                parameters.append(ActionParam(
                    name=name,
                    type=p_type,
                    options=p_options,
                    required=p_required,
                    description=f"Parameter {name}"
                ))
            kwargs["parameters"] = parameters

        action = AIAction(handler=handler, **kwargs)
        self.actions.append(action)
        if action_id:
            self._registered_ids.add(action_id)

    def bind_module(self, module: Any):
        """
        Scans a Python module for functions decorated with @landmark and registers them automatically.
        This provides auto-discovery for native Python, without requiring FastAPI.
        """
        import inspect
        for name, obj in inspect.getmembers(module):
            if inspect.isfunction(obj) or inspect.iscoroutinefunction(obj):
                meta = getattr(obj, "_llm_landmark", None)
                if meta and meta["id"] not in self._registered_ids:
                    extra = meta.get("extra", {})
                    self.register_action(
                        handler=obj,
                        id=meta["id"],
                        type=meta["type"],
                        description=meta["description"],
                        instructions=meta["instructions"],
                        **extra
                    )

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
    def _format_action_for_manifest(self, action, agent_view: bool, is_internal: bool) -> Dict[str, Any]:
        if agent_view and not is_internal:
            exclude_fields = {"groups", "global_access", "tags", "hidden", "headers", "context_dependencies", "required_auth"}
            return action.model_dump(exclude=exclude_fields, exclude_none=True)
        return action.model_dump(exclude_none=True)
