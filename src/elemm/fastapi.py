from fastapi import APIRouter, FastAPI, params, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from fastapi.security.base import SecurityBase
from typing import List, Dict, Any, Optional, Union, Tuple
from enum import Enum
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
        self.app_root_path = ""
        self.router = APIRouter()
        self._setup_well_known()

    def _setup_well_known(self):
        @self.router.api_route("/.well-known/llm-landmarks.json", methods=["GET", "HEAD"])
        async def get_protocol(group: Optional[str] = None, read_only: bool = False):
            try:
                return self.get_manifest(group=group, read_only=read_only)
            except Exception as e:
                logger.error(f"Error generating landmark manifest: {e}", exc_info=True)
                return {"error": "Internal error generating manifest", "version": self.version}

    def bind_to_app(self, app: FastAPI):
        """
        Scans all routes in the FastAPI app and registers those marked with @landmark.
        Also automatically registers the Agent-Repair-Kit to improve AI resilience.
        """
        self.app = app
        self.app_root_path = getattr(app, "root_path", "").rstrip("/")

        # 1. Register Agent-Repair-Kit (Exception Handler for LLM self-healing)
        @app.exception_handler(RequestValidationError)
        async def elemm_validation_exception_handler(request: Request, exc: RequestValidationError):
            return await self._agent_repair_handler(request, exc)
        
        # Ensure our manifest's openapi_url also respects the root_path if it's relative
        if self.openapi_url and self.openapi_url.startswith("/") and not self.openapi_url.startswith(self.app_root_path + "/"):
            self.openapi_url = f"{self.app_root_path}{self.openapi_url}"

        if self.debug:
            print(f"\n[elemm] 🔍 Starting Landmark discovery for app: {app.title} (root_path: '{self.app_root_path}')")
            
        # 1. Automatic Navigation via openapi_tags
        tags_meta = getattr(app, "openapi_tags", []) or []
        for tm in tags_meta:
            tag_name = tm.get("name")
            tag_desc = tm.get("description", f"Access module: {tag_name}")
            if tag_name:
                try:
                    tag_id = tag_name.lower().replace(" ", "_").replace("&", "and")
                    tag_id = "".join(c for c in tag_id if c.isalnum() or c == "_")
                    
                    self.register_action(
                        id=f"explore_{tag_id}",
                        type="navigation",
                        description=tag_desc,
                        instructions=f"Call this to discover tools related to {tag_name}.",
                        method="GET",
                        url=f"{self.app_root_path}/.well-known/llm-landmarks.json?group={tag_name}",
                        opens_group=tag_name,
                        groups=[] # Navigation tools are always in Root
                    )
                    if self.debug:
                        print(f"  [Discovery] Created Navigation Landmark for Tag: {tag_name}")
                except Exception as e:
                    logger.error(f"Failed to create navigation landmark for tag {tag_name}: {e}")

        count = 0
        for route in app.routes:
            if isinstance(route, APIRoute):
                try:
                    landmark_meta = getattr(route.endpoint, "_llm_landmark", None)
                    if landmark_meta:
                        self._register_from_route(route, landmark_meta)
                        count += 1
                        if self.debug:
                            print(f"  [Landmark] Registered '{landmark_meta['id']}' -> {route.methods} {route.path}")
                except Exception as e:
                    logger.error(f"Failed to register landmark from route {route.path}: {e}")
        
        if self.debug:
            print(f"[elemm] ✅ Discovery complete. Total landmarks: {count}\n")

    def _register_from_route(self, route: APIRoute, meta: Dict[str, Any]):
        method = list(route.methods)[0] if route.methods else "GET"
        url = route.path
        
        description = meta["description"] or route.endpoint.__doc__ or route.description or route.summary or ""
        description = description.strip()

        def map_type(annotation: Any) -> str:
            # Handle Optional/Union (get the first non-None type)
            origin = getattr(annotation, "__origin__", None)
            if origin is Union:
                args = getattr(annotation, "__args__", [])
                annotation = next((a for a in args if a != type(None)), annotation)
            
            raw_type = str(getattr(annotation, "__name__", annotation)).lower()
            
            # If it's a dict from JSON schema processing
            if isinstance(annotation, dict):
                raw_type = annotation.get("type", "string")

            mapping = {
                "str": "string", "string": "string",
                "int": "integer", "integer": "integer",
                "float": "number", "number": "number",
                "bool": "boolean", "boolean": "boolean",
                "list": "array", "array": "array",
                "dict": "object", "object": "object"
            }
            return mapping.get(raw_type, "string")

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
                        properties = schema.get("properties")
                        if not properties and "$ref" in schema:
                            # Handle Circular Refs (top-level $ref to $defs)
                            ref_name = schema["$ref"].split("/")[-1]
                            properties = schema.get("$defs", {}).get(ref_name, {}).get("properties", {})
                        
                        if not properties: properties = {}
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

                p_type = map_type(param.annotation)
                p_options = None
                
                # Enum detection
                enum_type = param.annotation
                # Handle Optional[Enum]
                origin = getattr(enum_type, "__origin__", None)
                if origin is Union:
                    args = getattr(enum_type, "__args__", [])
                    enum_type = next((a for a in args if a != type(None)), enum_type)
                
                if inspect.isclass(enum_type) and issubclass(enum_type, Enum):
                    p_options = [e.value for e in enum_type]
                
                actual_parameters.append(ActionParam(
                    name=name,
                    description=p_description,
                    type=p_type,
                    required=p_required,
                    managed_by=p_managed,
                    options=p_options,
                    default=None if p_required else (param.default.default if is_header else param.default)
                ))

        # Headers detection
        headers = meta["extra"].get("headers") or {}
        
        # Group extraction logic
        # Priority: Landmark 'groups' -> Landmark 'tags' -> FastAPI 'tags'
        groups = meta["extra"].get("groups") or meta["extra"].get("tags") or (route.tags if route.tags else [])

        # Action Registration
        self.register_action(
            id=meta["id"],
            type=meta["type"],
            tags=route.tags if route.tags else ["default"],
            groups=groups,
            opens_group=meta["extra"].get("opens_group"),
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
            hidden=meta["extra"].get("hidden", False),
            global_access=meta["extra"].get("global_access", False)
        )

    async def _agent_repair_handler(self, request: Request, exc: RequestValidationError):
        """Enriches validation errors with landmark 'remedy' instructions to help LLMs self-correct."""
        path_template = ""
        if "route" in request.scope:
            path_template = getattr(request.scope["route"], "path", "")
        
        method = request.method
        matched_action = None
        for action in self.actions:
            if action.url == path_template and action.method == method:
                matched_action = action
                break
        
        errors = exc.errors()
        if not matched_action:
            # Fallback to standard FastAPI format for non-landmark routes
            return JSONResponse(status_code=422, content={"detail": errors})

        response_body = {
            "status": "error",
            "error_type": "validation_failed",
            "managed_by": "elemm",
            "message": "The AI Agent sent an invalid request according to the landmark protocol.",
            "details": errors,
        }

        if matched_action.remedy:
            response_body["remedy"] = matched_action.remedy
            response_body["instruction"] = "Follow the 'remedy' above to fix your parameters and try again."
        
        # Noise Detection Heuristic
        try:
            received_params = []
            if method in ["POST", "PUT", "PATCH"]:
                body = await request.json()
                if isinstance(body, dict):
                    received_params = list(body.keys())
            
            allowed_params = []
            if matched_action.parameters:
                allowed_params += [p.name for p in matched_action.parameters]
            if matched_action.payload:
                if isinstance(matched_action.payload, list):
                    allowed_params += [p.name for p in matched_action.payload]
                elif isinstance(matched_action.payload, dict):
                    allowed_params += list(matched_action.payload.keys())
            
            spurious = [p for p in received_params if p not in allowed_params]
            if spurious:
                response_body["noise_warning"] = f"Action does not support these parameters: {spurious}. Stick to the manifest."
        except Exception:
            pass

        return JSONResponse(status_code=422, content=response_body)

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

# Official cool alias
Elemm = FastAPIProtocolManager
