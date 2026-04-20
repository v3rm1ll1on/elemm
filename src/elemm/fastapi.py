from fastapi import APIRouter, FastAPI, params, Request, Header
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
    def __init__(self, agent_welcome: str, version: str = "v1-lmlmm", openapi_url: str = "/api/openapi.json", protocol_instructions: Optional[str] = None, debug: bool = False, internal_access_key: Optional[str] = None):
        super().__init__(agent_welcome, version, protocol_instructions, internal_access_key=internal_access_key)
        self.openapi_url = openapi_url
        self.debug = debug
        self.app_root_path = ""
        self.router = APIRouter() # Keep for legacy compatibility if needed

    def bind_to_app(self, app: FastAPI):
        """
        Scans all routes in the FastAPI app and registers those marked with @landmark.
        Also automatically registers the Agent-Repair-Kit to improve AI resilience.
        """
        self.app = app
        self.app_root_path = getattr(app, "root_path", "").rstrip("/")

        # --- REGISTER ENDPOINT DIRECTLY ON APP ---
        @app.get("/.well-known/llm-landmarks.json", include_in_schema=False)
        @app.head("/.well-known/llm-landmarks.json", include_in_schema=False)
        async def get_protocol(
            group: Optional[str] = None, 
            read_only: bool = False,
            x_elemm_internal_key: Optional[str] = Header(None, alias="X-Elemm-Internal-Key")
        ):
            try:
                return self.get_manifest(group=group, read_only=read_only, internal_key=x_elemm_internal_key)
            except Exception as e:
                from .exceptions import LandmarkNotFoundError
                if isinstance(e, LandmarkNotFoundError):
                    return JSONResponse(status_code=404, content={"detail": str(e)})
                
                logger.error(f"Error generating landmark manifest: {e}", exc_info=True)
                return {"error": "Internal error generating manifest", "version": self.version}

        # --- REGISTER REPAIR KIT ---
        @app.exception_handler(RequestValidationError)
        async def elemm_validation_exception_handler(request: Request, exc: RequestValidationError):
            return await self._agent_repair_handler(request, exc)
        
        if self.openapi_url and self.openapi_url.startswith("/") and not self.openapi_url.startswith(self.app_root_path + "/"):
            self.openapi_url = f"{self.app_root_path}{self.openapi_url}"

        if self.debug:
            print(f"\n[elemm] 🔍 Starting Landmark discovery for app: {app.title} (root_path: '{self.app_root_path}')")
            
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
                        groups=[]
                    )
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
            origin = getattr(annotation, "__origin__", None)
            if origin is Union:
                args = getattr(annotation, "__args__", [])
                annotation = next((a for a in args if a != type(None)), annotation)
            raw_type = str(getattr(annotation, "__name__", annotation)).lower()
            if isinstance(annotation, dict): raw_type = annotation.get("type", "string")
            mapping = {"str": "string", "int": "integer", "float": "number", "bool": "boolean", "list": "array", "dict": "object"}
            return mapping.get(raw_type, "string")

        payload = meta["extra"].get("payload")
        if not payload:
            model = None
            if route.body_field: model = getattr(route.body_field, "annotation", None) or getattr(route.body_field, "type_", None)
            if not model and hasattr(route, "dependant") and route.dependant.body_params:
                for param in route.dependant.body_params:
                    model = getattr(param, "annotation", None) or getattr(param, "type_", None)
                    if model: break
            if not model:
                sig = inspect.signature(route.endpoint)
                for name, param in sig.parameters.items():
                    if hasattr(param.annotation, "model_json_schema") or hasattr(param.annotation, "schema"):
                        model = param.annotation
                        break
            if model:
                try:
                    schema = model.model_json_schema() if hasattr(model, "model_json_schema") else (model.schema() if hasattr(model, "schema") else None)
                    if schema:
                        properties = schema.get("properties", {})
                        if not properties and "$ref" in schema:
                            ref_name = schema["$ref"].split("/")[-1]
                            properties = schema.get("$defs", {}).get(ref_name, {}).get("properties", {})
                        required_fields = schema.get("required", [])
                        defs = schema.get("$defs", schema.get("definitions", {}))
                        payload = []
                        for field_name, field_info in properties.items():
                            if "$ref" in field_info:
                                ref_name = field_info["$ref"].split("/")[-1]
                                if ref_name in defs: field_info = {**defs[ref_name], **field_info}
                            payload.append(ActionParam(name=field_name, description=field_info.get("description", ""), type=map_type(field_info), required=field_name in required_fields, options=field_info.get("enum")))
                except Exception: pass

        sig = inspect.signature(route.endpoint)
        internal_fields = ["request", "response", "session_id", "headers", "background_tasks", "session"]
        actual_parameters = []
        context_deps = []
        for name, param in sig.parameters.items():
            if name in internal_fields:
                context_deps.append(name)
                continue
            is_security = isinstance(param.default, (params.Depends, params.Security)) and (isinstance(param.default.dependency, SecurityBase) or (inspect.isclass(param.default.dependency) and issubclass(param.default.dependency, SecurityBase)))
            if is_security:
                context_deps.append(name)
                meta["extra"]["required_auth"] = "bearer" if "bearer" in str(type(param.default.dependency)).lower() else "api-key"
                continue
            p_required = param.default == inspect.Parameter.empty
            actual_parameters.append(ActionParam(name=name, description=f"Parameter {name}", type=map_type(param.annotation), required=p_required))

        groups = meta["extra"].get("groups") or meta["extra"].get("tags") or (route.tags if route.tags else [])
        self.register_action(
            id=meta["id"], type=meta["type"], tags=route.tags or ["default"], groups=groups, opens_group=meta["extra"].get("opens_group"),
            description=description, instructions=meta.get("instructions"), remedy=meta["extra"].get("remedy"),
            method=method, url=url, parameters=actual_parameters, payload=payload, response_schema=self._extract_response_schema(route.response_model),
            hidden=meta["extra"].get("hidden", False), global_access=meta["extra"].get("global_access", False)
        )

    async def _agent_repair_handler(self, request: Request, exc: RequestValidationError):
        path_template = getattr(request.scope.get("route"), "path", "")
        method = request.method
        matched_action = next((a for a in self.actions if a.url == path_template and a.method == method), None)
        errors = exc.errors()
        if not matched_action: return JSONResponse(status_code=422, content={"detail": errors})
        res = {"status": "error", "error_type": "validation_failed", "managed_by": "elemm", "message": "Validation failed.", "details": errors}
        if matched_action.remedy: res["remedy"] = matched_action.remedy
        return JSONResponse(status_code=422, content=res)

    def _extract_response_schema(self, model: Any) -> Dict[str, str]:
        if not model: return None
        try:
            if hasattr(model, "model_json_schema"):
                return {k: v.get("type", "string") for k, v in model.model_json_schema().get("properties", {}).items()}
        except Exception: pass
        return None

    def get_router(self) -> APIRouter:
        return self.router

Elemm = FastAPIProtocolManager
