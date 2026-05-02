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
DEFAULT_PROTOCOL_INSTRUCTIONS = "ELEMM: [MNFST -> NAV -> EXEC]. Use 'execute_sequence' for BATCHING (multiple tools in one turn) and PIPING (chain results via N.field or N[index].field)."
#
# You should have received a copy of the GNU General Public License
# along with Elemm.  If not, see <https://www.gnu.org/licenses/>.

from fastapi import APIRouter, FastAPI, params, Request, Body, Header, Query
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.routing import APIRoute
from typing import List, Dict, Any, Optional, Union, Tuple
import logging
import httpx
import json
import inspect
from pydantic import BaseModel

from ...core.manager import BaseAIProtocolManager
from ...core.models import ActionParam
from ...core.discovery import map_type, resolve_refs
from .repair import agent_repair_handler
from .mcp import bind_mcp_sse, run_mcp_stdio
from ...core.context import session_headers

logger = logging.getLogger(__name__)

class FastAPIProtocolManager(BaseAIProtocolManager):
    """
    FastAPI-specific implementation of the Landmark Protocol.
    Supports automatic discovery of routes via .bind_to_app(app).
    """
    def __init__(self, 
                 app: Optional[FastAPI] = None, 
                 agent_welcome: Optional[str] = None,
                 agent_instructions: Optional[str] = None,
                 protocol_instructions: Optional[str] = None,
                 internal_access_key: Optional[str] = None,
                 hybrid_threshold: int = 10,
                 navigation_landmarks: Optional[List[Dict[str, Any]]] = None,
                 openapi_url: str = "/api/openapi.json", 
                 debug: bool = False):
        super().__init__(
            agent_welcome=agent_welcome,
            agent_instructions=agent_instructions,
            protocol_instructions=protocol_instructions,
            internal_access_key=internal_access_key,
            hybrid_threshold=hybrid_threshold,
            navigation_landmarks=navigation_landmarks
        )
        self.openapi_url = openapi_url
        self.debug = debug
        if debug:
            logger.setLevel(logging.INFO)
            if not logger.handlers:
                sh = logging.StreamHandler()
                sh.setFormatter(logging.Formatter('%(levelname)s:     %(message)s'))
                logger.addHandler(sh)

        self.app_root_path = ""
        self.router = APIRouter()
        self._setup_well_known(self.router)
        self._setup_navigation_tool(self.router)

    def _setup_navigation_tool(self, router_or_app: Union[APIRouter, FastAPI]):
        @router_or_app.get("/.well-known/module-navigation", include_in_schema=False)
        @self.tool(
            id="enter_module", 
            type="navigation",
            description="Enter a specific submodule or category of tools.",
            instructions="Use this to switch context and access domain-specific capabilities.",
            global_access=True
        )
        async def enter_module(module_name: str):
            """Internal navigation helper."""
            return {"message": f"Entered {module_name}. Inspect the landmark for new tools."}

    def bind_mcp_sse(self, app: FastAPI, route_prefix: str = "/mcp"):
        """Exposes the landmark protocol as an MCP SSE endpoint."""
        bind_mcp_sse(self, app, route_prefix)

    def run_mcp_stdio(self, app_import_path: str, host: str = "127.0.0.1", port: int = 8001):
        """Starts Web server and then runs MCP Stdio in main thread."""
        run_mcp_stdio(self, app_import_path, host, port)

    def _setup_well_known(self, router_or_app: Union[APIRouter, FastAPI]):
        @router_or_app.post("/.well-known/elemm/execute", include_in_schema=False)
        async def execute_protocol_action(
            request: Request,
            action_id: str = Body(..., embed=True),
            parameters: Dict[str, Any] = Body(default={}, embed=True),
            x_elemm_internal_key: Optional[str] = Header(None, alias="X-Elemm-Internal-Key")
        ):
            try:
                auth_headers = {k: v for k, v in request.headers.items() if k.lower() in ["authorization", "x-api-key", "api-key", "token", "cookie"]}
                current_sessions = session_headers.get().copy()
                current_sessions["elemm-internal"] = auth_headers
                token = session_headers.set(current_sessions)
                
                try:
                    result, status_code = await self.call_action(action_id, parameters)
                    if status_code >= 400 and isinstance(result, dict):
                        result["status"] = "error"
                        action = next((a for a in self.actions if a.id == action_id), None)
                        if action and getattr(action, "remedy", None):
                            result["remedy"] = action.remedy
                    return JSONResponse(status_code=status_code, content=result)
                finally:
                    session_headers.reset(token)
            except Exception as e:
                logger.error(f"Protocol Execution Error: {e}")
                return JSONResponse(status_code=400, content={"error": str(e), "hint": "Use 'get_manifest' to verify tools."})

        @router_or_app.get("/.well-known/elemm-manifest.md", include_in_schema=False)
        async def get_md_manifest(
            landmark_id: Optional[Union[str, List[str]]] = Query(None),
            technical: bool = Query(False)
        ):
            from ...mcp.manifest import ManifestGenerator
            from fastapi import Response
            generator = ManifestGenerator(self)
            try:
                if landmark_id:
                    md_content = generator.generate_landmark_detail(landmark_id)
                else:
                    md_content = generator.generate_summary()
                
                if technical:
                    md_content += generator.generate_technical_block(landmark_id)
                
                return Response(content=md_content, media_type="text/markdown")
            except Exception as e:
                logger.error(f"Failed to generate manifest: {e}")
                return Response(content=f"Error: {str(e)}", status_code=500)

    def bind_to_app(self, app: "FastAPI"):
        """Scans all routes in the FastAPI app and registers those marked with @landmark."""
        if hasattr(app, "_elemm_bound"): return
        app._elemm_bound = True
        self.app = app
        
        @app.exception_handler(HTTPException)
        async def elemm_http_exception_handler(request: Request, exc: HTTPException):
            detail = exc.detail
            message = detail if isinstance(detail, str) else detail.get("message", str(detail))
            remedy = detail.get("remedy", "Please check your parameters and retry.") if isinstance(detail, dict) else "Please check your parameters and retry."
            return JSONResponse(status_code=exc.status_code, content={"status": "error", "message": message, "remedy": remedy})

        self.app_root_path = getattr(app, "root_path", "").rstrip("/")
        self._setup_well_known(app)
        self._setup_navigation_tool(app)

        @app.exception_handler(RequestValidationError)
        async def elemm_validation_exception_handler(request: Request, exc: RequestValidationError):
            return await agent_repair_handler(self, request, exc)
        
        if self.openapi_url.startswith("/") and not self.openapi_url.startswith(self.app_root_path + "/"):
            self.openapi_url = f"{self.app_root_path}{self.openapi_url}"

        if self.debug: logger.info(f"Starting Landmark discovery for app: {app.title}")
            
        tags_meta = getattr(app, "openapi_tags", []) or []
        self._register_navigation_landmarks(app, tags_meta)

        count = 0
        for route in app.routes:
            if not isinstance(route, APIRoute): continue
            try:
                for method in route.methods:
                    if method not in ["GET", "POST", "PUT", "DELETE"]: continue
                    meta = self._get_route_metadata(route)
                    if meta:
                        self._register_from_route(route, meta)
                        count += 1
            except Exception as e:
                logger.error(f"Failed to register landmark from route {route.path}: {e}")
        
        if self.debug: logger.info(f"Discovery complete. Total actions registered: {count}")

    def _get_route_metadata(self, route: APIRoute) -> Optional[Dict[str, Any]]:
        meta = getattr(route.endpoint, "_llm_landmark", None)
        if not meta:
            matching_action = next((a for a in self.actions if a.handler == route.endpoint or (hasattr(route.endpoint, "__wrapped__") and a.handler == route.endpoint.__wrapped__)), None)
            if matching_action:
                meta = {"id": matching_action.id, "type": matching_action.type, "instructions": matching_action.instructions, "description": matching_action.description, "extra": {"remedy": matching_action.remedy, "groups": matching_action.groups, "global_access": matching_action.global_access}}
        if not meta and route.tags:
            meta = {"id": route.name, "type": "read", "extra": {}}
        return meta

    def _register_navigation_landmarks(self, app: FastAPI, tags_meta: List[Dict[str, Any]]):
        tag_descriptions = {tm.get("name"): tm.get("description") for tm in tags_meta if tm.get("name")}
        for tag_name, description in tag_descriptions.items():
            if not tag_name: continue
            purpose = description or f"Tools related to {tag_name}."
            if not self.navigation_landmarks: self.navigation_landmarks = []
            if not any(l.get("id") == tag_name for l in self.navigation_landmarks):
                self.navigation_landmarks.append({"id": tag_name, "notes": purpose})

    def _register_from_route(self, route: APIRoute, meta: Dict[str, Any]):
        method = list(route.methods)[0] if route.methods else "GET"
        meta_extra = meta.get("extra", {})
        doc = route.endpoint.__doc__.strip() if route.endpoint and route.endpoint.__doc__ else None
        instructions = (meta.get("instructions") or meta_extra.get("instructions") or "").strip()
        description = (meta.get("description") or meta_extra.get("description") or instructions or doc or route.description or route.summary or "").strip()

        payload = self._extract_payload(route, meta)
        actual_parameters, context_deps = self._extract_parameters(route, meta)

        # Group Unification: Decorator groups > Route tags > default
        groups = meta_extra.get("groups") or meta_extra.get("group") or (route.tags if route.tags else [])
        if isinstance(groups, str): groups = [groups]

        existing_action = next((a for a in self.actions if a.id == meta["id"]), None)
        handler = existing_action.handler if existing_action else route.endpoint

        if self.debug: logger.info(f"DEBUG: Registering Action '{meta['id']}' from route '{route.path}' [{method}]")

        self.register_action(
            handler=handler, 
            id=meta["id"], 
            type=meta["type"], 
            groups=groups, 
            opens_group=meta_extra.get("opens_group"), 
            description=description or "No description provided.", 
            instructions=instructions, 
            remedy=meta_extra.get("remedy"), 
            method=method, 
            url=route.path, 
            parameters=actual_parameters if actual_parameters else None, 
            headers=meta_extra.get("headers"), 
            payload=payload, 
            returns=meta_extra.get("returns"),
            required_auth=meta_extra.get("required_auth"), 
            context_dependencies=context_deps if context_deps else None, 
            response_schema=self._extract_response_schema(route.response_model), 
            hidden=meta_extra.get("hidden", False), 
            global_access=meta_extra.get("global_access", False)
        )

    def _extract_payload(self, route: APIRoute, meta: Dict[str, Any]) -> Optional[Union[List[ActionParam], Dict[str, Any]]]:
        payload = meta["extra"].get("payload")
        if payload: return payload
        
        body_params = route.dependant.body_params if hasattr(route, "dependant") and route.dependant.body_params else ([route.body_field] if route.body_field else [])
        if not body_params: return None

        if len(body_params) == 1:
            res = self._extract_pydantic_payload(body_params[0])
            if res: return res

        discovered_params = []
        for param in body_params:
            field_info = getattr(param, "field_info", None)
            from pydantic_core import PydanticUndefined
            required = (field_info.default is PydanticUndefined and field_info.default_factory is None) if field_info else True
            discovered_params.append(ActionParam(name=param.name, description=getattr(field_info, "description", "") or "", required=required))
        return discovered_params if discovered_params else None

    def _extract_pydantic_payload(self, param: Any) -> Optional[List[ActionParam]]:
        model = getattr(param, "annotation", None)
        if model is None or model is inspect.Signature.empty: model = getattr(param, "type_", None)
        if (model is None or model is inspect.Signature.empty) and hasattr(param, "field_info"): model = getattr(param.field_info, "annotation", None)

        try:
            if not (model and ((inspect.isclass(model) and issubclass(model, BaseModel)) or hasattr(model, "model_json_schema") or hasattr(model, "schema"))): return None
            schema = model.model_json_schema() if hasattr(model, "model_json_schema") else model.schema()
            resolved_schema = resolve_refs(schema, schema.get("$defs", schema.get("definitions", {})))
            properties = resolved_schema.get("properties", {})
            required_fields = resolved_schema.get("required", [])
            
            payload_params = []
            for field_name, field_info in properties.items():
                p_type, p_options = map_type(field_info)
                payload_params.append(ActionParam(name=field_name, description=field_info.get("description", f"Field {field_name}"), type=p_type, required=field_name in required_fields, default=field_info.get("default"), example=field_info.get("example"), options=p_options or field_info.get("enum"), min_value=field_info.get("minimum") or field_info.get("ge"), max_value=field_info.get("maximum") or field_info.get("le")))
            return payload_params
        except Exception as e:
            logger.warning(f"Could not extract schema from model {model}: {e}")
        return None

    def _extract_parameters(self, route: APIRoute, meta: Dict[str, Any]) -> Tuple[List[ActionParam], List[str]]:
        manual_params = meta["extra"].get("parameters")
        if manual_params:
            return [ActionParam(name=p["name"], description=p.get("description", f"Parameter {p['name']}"), type=p.get("type", "string"), required=p.get("required", True), default=p.get("default"), managed_by="protocol" if p["name"].lower() in ["authorization", "x-api-key", "token"] else None) for p in manual_params], []

        sig = inspect.signature(route.endpoint)
        internal_fields = ["request", "response", "session_id", "headers", "background_tasks", "session"]
        actual_parameters, context_deps = [], []
        
        for name, param in sig.parameters.items():
            if name in internal_fields or isinstance(param.default, params.Depends) or (inspect.isclass(param.annotation) and issubclass(param.annotation, BaseModel)):
                context_deps.append(name)
                continue
            actual_parameters.append(self._process_single_parameter(name, param))
        return actual_parameters, context_deps

    def _process_single_parameter(self, name: str, param: inspect.Parameter) -> ActionParam:
        p_description, p_required, p_managed, p_default_val = f"Parameter {name}", param.default == inspect.Parameter.empty, None, None
        
        source = param.default if isinstance(param.default, params.Param) else param
        if isinstance(param.default, params.Param):
            if param.default.description: p_description = param.default.description
            if isinstance(param.default, params.Header) and name.lower() in ["authorization", "x-api-key", "api-key", "token", "auth"]: p_managed = "protocol"
        
        val = getattr(source, "default", None) if source is not param else param.default
        try:
            json.dumps(val)
            p_default_val = val if val is not Ellipsis else None
        except: pass
        if val is Ellipsis or "PydanticUndefined" in str(val): p_required = True

        p_type, p_options = map_type(param.annotation)
        return ActionParam(name=name, description=p_description, type=p_type, required=p_required, managed_by=p_managed, options=p_options, default=p_default_val)

    def _extract_response_schema(self, model: Any) -> Dict[str, Any]:
        if not model: return {}
        try:
            origin = getattr(model, "__origin__", None)
            args = getattr(model, "__args__", [])
            if origin in [list, List] and args: model = args[0]
            elif origin in [Union, Optional] and args: model = next((a for a in args if a != type(None)), model)

            if hasattr(model, "model_json_schema"):
                props = model.model_json_schema().get("properties", {})
                return {k: ({"type": v.get("type", "string"), "description": v.get("description", "")} if v.get("description") else v.get("type", "string")) for k, v in props.items()}
        except Exception: return {"info": "Complex response model"}
        return None

    def tool(self, **kwargs):
        def decorator(func):
            if "id" not in kwargs:
                kwargs["id"] = func.__name__
            kwargs.setdefault("type", "read")
            func._llm_landmark = {"id": kwargs["id"], "type": kwargs["type"], "description": kwargs.get("description"), "extra": kwargs}
            # We don't register here, bind_to_app will do it. 
            # But we can pre-register if bind_to_app was already called.
            if hasattr(self, "app"):
                self.register_action(handler=func, **kwargs)
            return func
        return decorator

    def action(self, **kwargs):
        kwargs.setdefault("type", "write")
        return self.tool(**kwargs)

    async def call_action(self, action_id: str, arguments: Dict[str, Any]) -> tuple[Any, int]:
        action = next((a for a in self.actions if a.id == action_id), None)
        if not action: raise ValueError(f"Action {action_id} not found.")
        params_to_use = (arguments or {}).copy()
        
        if not action.url:
            try:
                sig = inspect.signature(action.handler)
                filtered_params = {k: v for k, v in params_to_use.items() if k in sig.parameters}
                result = await action.handler(**filtered_params) if inspect.iscoroutinefunction(action.handler) else action.handler(**filtered_params)
                return result, 200
            except Exception as e:
                logger.error(f"Native Execution Error for {action_id}: {e}")
                return {"error": str(e)}, 500

        url = action.url
        for k in list(params_to_use.keys()):
            if f"{{{k}}}" in url: url = url.replace(f"{{{k}}}", str(params_to_use.pop(k)))

        from urllib.parse import urlparse
        host_key = urlparse(url).netloc or "elemm-internal"
        current_headers = session_headers.get().get(host_key, {})
        
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://elemm-internal") as client:
            method = (action.method or "POST").upper()
            kwargs = {"headers": current_headers}
            if method in ["GET", "DELETE"]: kwargs["params"] = params_to_use
            else: kwargs["json"] = params_to_use
            resp = await client.request(method, url, **kwargs)
            
            if self.debug:
                status_msg = "OK" if resp.status_code < 400 else "ERROR"
                logger.info(f"INTERNAL: \"{method} {url} HTTP/1.1\" {resp.status_code} {status_msg}")

            try: result = resp.json()
            except: result = {"status": "ok", "message": resp.text}
            
            if resp.status_code >= 400 and isinstance(result, dict):
                result["status"] = "error"
                if action.remedy: result["remedy"] = action.remedy
                elif resp.status_code == 404:
                    import re
                    placeholders = re.findall(r"\{(\w+)\}", url)
                    result["remedy"] = f"Missing arguments: {', '.join(placeholders)}." if placeholders else "Action not found."
            return result, resp.status_code

    def get_router(self) -> APIRouter:
        return self.router

Elemm = FastAPIProtocolManager
