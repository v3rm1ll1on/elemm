from fastapi import APIRouter, FastAPI, params
from fastapi.routing import APIRoute
from fastapi.security.base import SecurityBase
from typing import List, Dict, Any, Optional, Union, Tuple
import inspect
import logging

from .base import BaseAIProtocolManager
from .models import ActionParam

logger = logging.getLogger(__name__)

class FastAPIProtocolManager(BaseAIProtocolManager):
    """
    FastAPI-specific implementation of the Landmark Protocol.
    Supports automatic discovery of routes via .bind_to_app(app).
    """
    def __init__(self, agent_welcome: str, version: str = "v1-lmlmm", openapi_url: str = "/api/openapi.json", protocol_instructions: Optional[str] = None, debug: bool = False):
        super().__init__(agent_welcome, version, protocol_instructions)
        self.openapi_url = openapi_url
        self.debug = debug
        self.router = APIRouter()
        self._setup_well_known()

    def _setup_well_known(self):
        @self.router.api_route("/.well-known/llm-landmarks.json", methods=["GET", "HEAD"])
        async def get_protocol():
            return self.get_manifest()

    def bind_to_app(self, app: FastAPI):
        """
        Scans all routes in the FastAPI app and registers those marked with @landmark.
        """
        if self.debug:
            print(f"\n[elemm] 🔍 Starting Landmark discovery for app: {app.title}")
            
        count = 0
        for route in app.routes:
            if isinstance(route, APIRoute):
                landmark_meta = getattr(route.endpoint, "_llm_landmark", None)
                if landmark_meta:
                    self._register_from_route(route, landmark_meta)
                    count += 1
                    if self.debug:
                        print(f"  [Landmark] Registered '{landmark_meta['id']}' -> {route.methods} {route.path}")
        
        if self.debug:
            print(f"[elemm] ✅ Discovery complete. Total landmarks: {count}\n")

    def _register_from_route(self, route: APIRoute, meta: Dict[str, Any]):
        method = list(route.methods)[0] if route.methods else "GET"
        url = route.path
        
        description = meta["description"] or route.endpoint.__doc__ or route.description or route.summary or ""
        description = description.strip()

        def map_type(field_info: Dict[str, Any]) -> str:
            raw_type = field_info.get("type")
            if not raw_type:
                options = field_info.get("anyOf") or field_info.get("oneOf")
                if options:
                    for opt in options:
                        if opt.get("type") and opt.get("type") != "null":
                            raw_type = opt.get("type")
                            break
            
            mapping = {
                "str": "string", "string": "string",
                "int": "integer", "integer": "integer",
                "float": "number", "number": "number",
                "bool": "boolean", "boolean": "boolean",
                "list": "array", "array": "array",
                "dict": "object", "object": "object"
            }
            return mapping.get(raw_type, raw_type or "string")

        # Automatic payload detection
        payload = meta["extra"].get("payload")
        
        if not payload:
            model = None
            
            # 1. Check official FastAPI body_field
            if route.body_field:
                model = getattr(route.body_field, "annotation", None) or \
                        getattr(route.body_field, "type_", None)
            
            # 2. Check body_params in dependencies
            if not model and hasattr(route, "dependant") and route.dependant.body_params:
                for param in route.dependant.body_params:
                    model = getattr(param, "annotation", None) or getattr(param, "type_", None)
                    if model: break
            
            # 3. Fallback: Direct inspection of the endpoint signature
            if not model:
                sig = inspect.signature(route.endpoint)
                for name, param in sig.parameters.items():
                    ann = param.annotation
                    # Check if it looks like a Pydantic model
                    if hasattr(ann, "model_json_schema") or hasattr(ann, "schema"):
                        model = ann
                        break

            if model:
                try:
                    schema = model.model_json_schema() if hasattr(model, "model_json_schema") else (model.schema() if hasattr(model, "schema") else None)
                    if schema:
                        properties = schema.get("properties", {})
                        required_fields = schema.get("required", [])
                        defs = schema.get("$defs", schema.get("definitions", {}))
                        
                        payload = []
                        for field_name, field_info in properties.items():
                            # Resolve $ref for Enums and other types
                            if "$ref" in field_info:
                                ref_path = field_info["$ref"].split("/")
                                ref_name = ref_path[-1]
                                if ref_name in defs:
                                    field_info = {**defs[ref_name], **field_info}
                            
                            p_type = map_type(field_info)
                            payload.append(ActionParam(
                                name=field_name,
                                description=field_info.get("description", f"Field {field_name}"),
                                type=p_type,
                                required=field_name in required_fields,
                                default=field_info.get("default"),
                                example=field_info.get("example"),
                                options=field_info.get("enum"), # Extract Enums!
                                min_value=field_info.get("minimum") or field_info.get("ge"),
                                max_value=field_info.get("maximum") or field_info.get("le")
                            ))
                except Exception as e:
                    logger.warning(f"Could not extract schema from model {model}: {e}")

        # Parameter detection
        manual_params = meta["extra"].get("parameters")
        actual_parameters = []
        context_deps = []
        
        if manual_params:
            for p in manual_params:
                actual_parameters.append(ActionParam(
                    name=p["name"],
                    description=p.get("description", f"Parameter {p['name']}"),
                    type=p.get("type", "string"),
                    required=p.get("required", True),
                    default=p.get("default"),
                    managed_by="protocol" if p["name"].lower() in ["authorization", "x-api-key", "token"] else None
                ))
        else:
            # Fallback to automatic inspection
            sig = inspect.signature(route.endpoint)
            # Standard fields to ignore/treat as context
            internal_fields = ["request", "response", "session_id", "headers", "background_tasks", "session"]
            
            for name, param in sig.parameters.items():
                if name in internal_fields:
                    context_deps.append(name)
                    continue
                
                # Metadata detection
                p_description = f"Parameter {name}"
                p_required = param.default == inspect.Parameter.empty
                p_managed = None
                p_type = "string"
                is_header = False
                
                # 1. Check for explicit Header parameters
                if isinstance(param.default, params.Header):
                    is_header = True
                    # Protection (Critic Point 2): Mark sensitive headers as protocol-managed
                    if name.lower() in ["authorization", "x-api-key", "api-key", "token", "auth"]:
                        p_managed = "protocol"
                    
                    if param.default.description:
                        p_description = param.default.description
                    else:
                        p_description = f"Parameter {name} (Header)"
                    
                    # Check if Header is required
                    if param.default.default is Ellipsis or str(param.default.default) == "PydanticUndefined":
                        p_required = True
                
                # 2. Check for Security/Depends dependencies
                elif isinstance(param.default, (params.Depends, params.Security)):
                    dependency = param.default.dependency
                    
                    # Inspect if the dependency is a Security Scheme (like HTTPBearer, APIKeyHeader)
                    is_security = isinstance(dependency, SecurityBase) or \
                                 (inspect.isclass(dependency) and issubclass(dependency, SecurityBase))
                    
                    if is_security:
                        # Auto-detect Auth requirements
                        context_deps.append(name)
                        p_managed = "protocol"
                        # We try to extract the auth type (e.g., 'bearer', 'api-key')
                        auth_type = "bearer" if "bearer" in str(type(dependency)).lower() else "api-key"
                        meta["extra"]["required_auth"] = auth_type
                        continue 
                    
                    # Standard dependencies that look like auth should also be context-only
                    if "get_current_user" in str(dependency) or "auth" in str(dependency).lower():
                        context_deps.append(name)
                        continue
                    
                    # If it's not a security scheme, we might want to skip it as it's internal logic
                    context_deps.append(name)
                    continue

                if param.annotation == int: p_type = "integer"
                elif param.annotation == float: p_type = "number"
                elif param.annotation == bool: p_type = "boolean"
                
                actual_parameters.append(ActionParam(
                    name=name,
                    description=p_description,
                    type=p_type,
                    required=p_required,
                    managed_by=p_managed,
                    default=None if p_required else (None if is_header else param.default)
                ))

        # Headers detection
        headers = meta["extra"].get("headers") or {}
        
        # Action Registration
        self.register_action(
            id=meta["id"],
            type=meta["type"],
            tags=route.tags if route.tags else ["default"],
            description=description or "No description provided.",
            instructions=meta.get("instructions"),
            remedy=meta["extra"].get("remedy"),
            method=method,
            url=url,
            parameters=actual_parameters if actual_parameters else None,
            headers=headers if headers else None,
            payload=payload,
            required_auth=meta["extra"].get("required_auth"),
            context_dependencies=context_deps if context_deps else None,
            response_schema=self._extract_response_schema(route.response_model),
            hidden=meta["extra"].get("hidden", False)
        )

    def _extract_response_schema(self, model: Any) -> Dict[str, str]:
        if not model: return {}
        try:
            # Handle List[T], Optional[T], etc.
            origin = getattr(model, "__origin__", None)
            args = getattr(model, "__args__", [])
            if origin in [list, List] and args:
                model = args[0]
            elif origin in [Union, Optional] and args:
                # Take first non-None type
                model = next((a for a in args if a != type(None)), model)

            if hasattr(model, "model_json_schema"):
                schema = model.model_json_schema()
                props = schema.get("properties", {})
                res = {}
                for k, v in props.items():
                    # Return a dict for each property to include description if present
                    prop_type = v.get("type", "string")
                    desc = v.get("description", "")
                    if desc:
                        res[k] = {"type": prop_type, "description": desc}
                    else:
                        res[k] = prop_type
                return res
        except Exception:
            return {"info": "Complex response model"}
        return None

    def get_router(self) -> APIRouter:
        return self.router
