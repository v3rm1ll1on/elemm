from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute
from typing import List, Dict, Any, Optional, Union
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
    def __init__(self, agent_welcome: str, version: str = "v1-lmlmm", openapi_url: str = "/api/openapi.json", protocol_instructions: Optional[str] = None):
        super().__init__(agent_welcome, version, protocol_instructions)
        self.openapi_url = openapi_url
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
        for route in app.routes:
            if isinstance(route, APIRoute):
                landmark_meta = getattr(route.endpoint, "_llm_landmark", None)
                if landmark_meta:
                    self._register_from_route(route, landmark_meta)

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
                        
                        payload = []
                        for field_name, field_info in properties.items():
                            p_type = map_type(field_info)
                            payload.append(ActionParam(
                                name=field_name,
                                description=field_info.get("description", f"Field {field_name}"),
                                type=p_type,
                                required=field_name in required_fields,
                                default=field_info.get("default"),
                                min_value=field_info.get("minimum") or field_info.get("ge"),
                                max_value=field_info.get("maximum") or field_info.get("le")
                            ))
                except Exception as e:
                    logger.warning(f"Could not extract schema from model {model}: {e}")

        # Parameter detection
        params = meta["extra"].get("params") or {}
        headers = meta["extra"].get("headers") or {}
        actual_parameters = []
        
        sig = inspect.signature(route.endpoint)
        for name, param in sig.parameters.items():
            if name in ["request", "response", "session_id", "headers"] or name in headers:
                continue
            if route.body_field and name == route.body_field.name:
                continue

            is_optional = param.default is not inspect.Parameter.empty
            raw_annotation = param.annotation
            
            # Extract underlying type for Optional[T]
            p_type_name = "string"
            if hasattr(raw_annotation, "__origin__") and (raw_annotation.__origin__ is Union or str(raw_annotation.__origin__) == "typing.Union"):
                args = [a for a in raw_annotation.__args__ if a is not type(None)]
                if args: p_type_name = args[0].__name__.lower() if hasattr(args[0], "__name__") else str(args[0])
            elif hasattr(raw_annotation, "__name__"):
                p_type_name = raw_annotation.__name__.lower()
            
            p_type = map_type({"type": p_type_name})

            manual_override = params.get(name, {})
            if isinstance(manual_override, str): manual_override = {"description": manual_override}
            
            actual_parameters.append(ActionParam(
                name=name,
                description=manual_override.get("description") or f"Parameter {name}",
                type=manual_override.get("type") or p_type,
                required=manual_override.get("required") if "required" in manual_override else not is_optional,
                default=manual_override.get("default") if "default" in manual_override else (None if not is_optional else param.default)
            ))

        self.register_action(
            id=meta["id"],
            type=meta["type"],
            description=description or "No description provided.",
            instructions=meta.get("instructions"),
            method=method,
            url=url,
            parameters=actual_parameters if actual_parameters else None,
            headers=headers if headers else None,
            payload=payload,
            required_auth=meta["extra"].get("required_auth"),
            response_schema=self._extract_response_schema(route),
            hidden=meta["extra"].get("hidden", False)
        )

    def _extract_response_schema(self, route: APIRoute) -> Optional[Dict[str, Any]]:
        if not route.response_model: return None
        try:
            model = route.response_model
            if hasattr(model, "model_json_schema"):
                schema = model.model_json_schema()
                props = schema.get("properties", {})
                simplified = {k: v.get("type", "any") for k, v in props.items()}
                return simplified
        except Exception:
            return {"info": "Complex response model"}
        return None

    def get_router(self) -> APIRouter:
        return self.router
