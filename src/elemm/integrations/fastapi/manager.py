from fastapi import APIRouter, FastAPI, params, Request, Body, Header
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.routing import APIRoute
from typing import List, Dict, Any, Optional, Union, Tuple, Callable
import logging
import httpx
import json
import inspect
import re
import uuid
from contextvars import ContextVar
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
            # Also ensure a handler exists if not already configured
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
        from fastapi import Header

        @router_or_app.post("/.well-known/elemm/execute", include_in_schema=False)
        async def execute_protocol_action(
            request: Request,
            action_id: str = Body(..., embed=True),
            parameters: Dict[str, Any] = Body(default={}, embed=True),
            x_elemm_internal_key: Optional[str] = Header(None, alias="X-Elemm-Internal-Key")
        ):
            try:
                # Scoped Auth: Propagate incoming headers (e.g. Authorization) to internal call
                # We filter for common auth headers to avoid bloat
                auth_headers = {}
                for k, v in request.headers.items():
                    if k.lower() in ["authorization", "x-api-key", "api-key", "token", "cookie"]:
                        auth_headers[k] = v
                
                # Merge with current host context (usually elemm-internal for the server-side app)
                current_sessions = session_headers.get().copy()
                current_sessions["elemm-internal"] = auth_headers
                token = session_headers.set(current_sessions)
                
                try:
                    # We use the internal call_action which handles routing and auth
                    result, status_code = await self.call_action(action_id, parameters)
                    
                    # Protocol Enrichment: If the action failed (>=400), inject the tool-specific remedy
                    if status_code >= 400 and isinstance(result, dict):
                        action = next((a for a in self.actions if a.id == action_id), None)
                        if action and getattr(action, "remedy", None):
                            result["remedy"] = action.remedy
                    
                    return JSONResponse(status_code=status_code, content=result)
                finally:
                    session_headers.reset(token)
            except Exception as e:
                logger.error(f"Protocol Execution Error: {e}")
                return JSONResponse(
                    status_code=400, 
                    content={
                        "error": str(e), 
                        "hint": "The action you requested could not be executed. Use 'get_manifest' to verify available tools."
                    }
                )

        @router_or_app.get("/.well-known/elemm-manifest.md", include_in_schema=False)
        async def get_md_manifest(request: Request, landmark_id: Optional[str] = None, part: Optional[str] = None, technical: bool = False):
            from ...mcp.manifest import ManifestGenerator
            from fastapi import Response
            
            # Split comma-separated parts if provided
            parts = part.split(",") if part else None
            
            try:
                if landmark_id:
                    # Filter tools for the specific landmark
                    actions = []
                    for a in self.actions:
                        groups = a.groups if hasattr(a, "groups") else []
                        if landmark_id in groups:
                            actions.append({
                                "id": a.id if hasattr(a, "id") else "",
                                "description": a.description if hasattr(a, "description") else ""
                            })
                    
                    md_content = ManifestGenerator.generate_detailed_landmark(landmark_id, actions)
                else:
                    md_content = ManifestGenerator.generate_markdown(
                        manager=self,
                        system_name=self.agent_welcome or "Elemm Protocol",
                        instructions=self.protocol_instructions or "",
                        landmarks=self.navigation_landmarks or [],
                        include_technical_metadata=technical,
                        parts=parts or (["landmarks"] if not self.debug else ["welcome", "instructions", "landmarks"])
                    )
            except Exception as e:
                logger.error(f"Failed to generate manifest: {e}")
                md_content = f"# ELEMM PROTOCOL ERROR\n\n## Internal Error\n{str(e)}\n\n## Remedy\nPlease try to refresh the session or use the 'navigate' tool to recover."
            
            return Response(content=md_content, media_type="text/markdown")

    def bind_to_app(self, app: "FastAPI"):
        """Scans all routes in the FastAPI app and registers those marked with @landmark."""
        if hasattr(app, "_elemm_bound"):
            return
        app._elemm_bound = True
        self.app = app
        
        # 1. Register Global Elemm Error Handler
        @app.exception_handler(HTTPException)
        async def elemm_http_exception_handler(request: Request, exc: HTTPException):
            detail = exc.detail
            message = detail if isinstance(detail, str) else detail.get("message", str(detail))
            
            # Try to find a tool-specific remedy if it exists in our registry
            # This allows even generic 404s to carry protocol remedies
            remedy = "Please check your parameters and retry."
            if isinstance(detail, dict) and "remedy" in detail:
                remedy = detail["remedy"]
            
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "status": "error",
                    "message": message,
                    "remedy": remedy
                }
            )

        # 2. Setup internal routes and discovery
        self.app_root_path = getattr(app, "root_path", "").rstrip("/")
        self._setup_well_known(app)
        self._setup_navigation_tool(app)

        @app.exception_handler(RequestValidationError)
        async def elemm_validation_exception_handler(request: Request, exc: RequestValidationError):
            return await agent_repair_handler(self, request, exc)
        
        if self.openapi_url and self.openapi_url.startswith("/") and not self.openapi_url.startswith(self.app_root_path + "/"):
            self.openapi_url = f"{self.app_root_path}{self.openapi_url}"

        if self.debug:
            logger.info(f"Starting Landmark discovery for app: {app.title}")
            
        # 1. Navigation Discovery
        tags_meta = getattr(app, "openapi_tags", []) or []
        self._register_navigation_landmarks(app, tags_meta)

        # 2. Tool Discovery
        count = 0
        for route in app.routes:
            if isinstance(route, APIRoute):
                try:
                    # Strategy 1: Explicit Attribute (Fastest)
                    endpoint = route.endpoint
                    landmark_meta = getattr(endpoint, "_llm_landmark", None)
                    
                    if not landmark_meta and hasattr(endpoint, "__wrapped__"):
                        endpoint = endpoint.__wrapped__
                        landmark_meta = getattr(endpoint, "_llm_landmark", None)

                    if landmark_meta:
                        self._register_from_route(route, landmark_meta)
                        count += 1
                    else:
                        # Strategy 2: Match by handler (fallback for decorated functions)
                        # Find any action that was pre-registered via @tool/@action
                        matching_action = next((a for a in self.actions if a.handler == route.endpoint or (hasattr(route.endpoint, "__wrapped__") and a.handler == route.endpoint.__wrapped__)), None)
                        if matching_action:
                            # Re-register to pick up URL/Method from route
                            fake_meta = {
                                "id": matching_action.id, 
                                "type": matching_action.type, 
                                "description": matching_action.description,
                                "instructions": matching_action.instructions,
                                "extra": {
                                    "remedy": matching_action.remedy,
                                    "global_access": matching_action.global_access,
                                    "groups": matching_action.groups
                                }
                            }
                            self._register_from_route(route, fake_meta)
                            count += 1
                            pass
                except Exception as e:
                    logger.error(f"Failed to register landmark from route {route.path}: {e}")
        
        if self.debug:
            logger.info(f"Discovery complete. Total actions registered: {count}")

    def _register_navigation_landmarks(self, app: FastAPI, tags_meta: List[Dict[str, Any]]):
        known_tags = {tm.get("name") for tm in tags_meta if tm.get("name")}
        
        # Add tags from routes
        for route in app.routes:
            if isinstance(route, APIRoute) and route.tags:
                for tag in route.tags:
                    if tag not in known_tags:
                        tags_meta.append({"name": tag})
                        known_tags.add(tag)

        # Tag meta dictionary for lookup
        tag_descriptions = {tm.get("name"): tm.get("description") for tm in tags_meta if tm.get("name")}

        for tag_name, description in tag_descriptions.items():
            if not tag_name: continue
            
            try:
                tag_id = "".join(c for c in tag_name.lower().replace(" ", "_").replace("&", "and") if c.isalnum() or c == "_")
                purpose = description if description else f"tools related to {tag_name}."
                
                self.register_action(
                    id=f"explore_{tag_id}",
                    type="navigation",
                    description=f"Navigate to {tag_name}: {purpose}",
                    instructions=f"Call this when your investigation requires access to {tag_name} specific capabilities.",
                    method="GET",
                    # Internal discovery endpoint
                    url=f"{self.app_root_path}/.well-known/elemm/discovery?group={tag_name}",
                    opens_group=tag_name,
                    groups=[] 
                )
                
                # Auto-populate navigation_landmarks for manifest generation
                if not self.navigation_landmarks:
                    self.navigation_landmarks = []
                
                if not any(l.get("id") == tag_name for l in self.navigation_landmarks):
                    self.navigation_landmarks.append({
                        "id": tag_name,
                        "notes": purpose
                    })
            except Exception as e:
                logger.error(f"Failed to create navigation landmark for tag {tag_name}: {e}")

    def _register_from_route(self, route: APIRoute, meta: Dict[str, Any]):
        method = list(route.methods)[0] if route.methods else "GET"
        url = route.path
        
        # LLM Metadata Hierarchy: instructions > description > docstring
        doc = route.endpoint.__doc__.strip() if route.endpoint and route.endpoint.__doc__ else None
        description = (meta.get("instructions") or meta.get("description") or doc or route.description or route.summary or "").strip()
        instructions = meta.get("instructions") or ""

        payload = self._extract_payload(route, meta)
        actual_parameters, context_deps = self._extract_parameters(route, meta)

        extra = meta.get("extra", {})
        groups = extra.get("groups") or extra.get("group") or extra.get("tags") or (route.tags if route.tags else [])
        if isinstance(groups, str):
            groups = [groups]

        # Preserve existing handler if this ID was already registered via decorator
        existing_action = next((a for a in self.actions if a.id == meta["id"]), None)
        handler = existing_action.handler if existing_action else route.endpoint

        if self.debug:
            logger.info(f"DEBUG: Registering Action '{meta['id']}' from route '{route.path}' [{method}]")

        self.register_action(
            handler=handler,
            id=meta["id"],
            type=meta["type"],
            tags=route.tags if route.tags else ["default"],
            groups=groups,
            opens_group=meta["extra"].get("opens_group"),
            description=description or "No description provided.",
            instructions=instructions,
            remedy=meta["extra"].get("remedy"),
            method=method,
            url=url,
            parameters=actual_parameters if actual_parameters else None,
            headers=meta["extra"].get("headers") or None,
            payload=payload,
            required_auth=meta["extra"].get("required_auth"),
            context_dependencies=context_deps if context_deps else None,
            response_schema=self._extract_response_schema(route.response_model),
            hidden=meta["extra"].get("hidden", False),
            global_access=meta["extra"].get("global_access", False)
        )

    def _extract_payload(self, route: APIRoute, meta: Dict[str, Any]) -> Optional[Union[List[ActionParam], Dict[str, Any]]]:
        payload = meta["extra"].get("payload")
        if payload: return payload
        
        model = None
        if route.body_field:
            model = getattr(route.body_field, "annotation", None) or getattr(route.body_field, "type_", None)
        
        if not model and hasattr(route, "dependant") and route.dependant.body_params:
            for param in route.dependant.body_params:
                model = getattr(param, "annotation", None) or getattr(param, "type_", None)
                if model: break
        
        if not model:
            sig = inspect.signature(route.endpoint)
            for name, param in sig.parameters.items():
                ann = param.annotation
                if hasattr(ann, "model_json_schema") or hasattr(ann, "schema"):
                    model = ann
                    break

        if not model: return None
        
        try:
            schema = model.model_json_schema() if hasattr(model, "model_json_schema") else (model.schema() if hasattr(model, "schema") else None)
            if not schema: return None
            
            defs = schema.get("$defs", schema.get("definitions", {}))
            resolved_schema = resolve_refs(schema, defs)
            
            properties = resolved_schema.get("properties", {})
            required_fields = resolved_schema.get("required", [])
            
            payload_params = []
            for field_name, field_info in properties.items():
                p_type, p_options = map_type(field_info)
                payload_params.append(ActionParam(
                    name=field_name,
                    description=field_info.get("description", f"Field {field_name}"),
                    type=p_type,
                    required=field_name in required_fields,
                    default=field_info.get("default"),
                    example=field_info.get("example"),
                    options=p_options or field_info.get("enum"),
                    min_value=field_info.get("minimum") or field_info.get("ge"),
                    max_value=field_info.get("maximum") or field_info.get("le")
                ))
            return payload_params
        except Exception as e:
            logger.warning(f"Could not extract schema from model {model}: {e}")
            return None

    def _extract_parameters(self, route: APIRoute, meta: Dict[str, Any]) -> Tuple[List[ActionParam], List[str]]:
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
            return actual_parameters, context_deps

        sig = inspect.signature(route.endpoint)
        internal_fields = ["request", "response", "session_id", "headers", "background_tasks", "session"]
        
        for name, param in sig.parameters.items():
            # Context dependencies: Parameters that are injected by FastAPI/Elemm and NOT provided by the LLM
            is_dependency = isinstance(param.default, params.Depends)
            
            # Filter out Pydantic BaseModels from path/query parameters since they are handled by payload
            is_model = inspect.isclass(param.annotation) and issubclass(param.annotation, BaseModel)
            
            if name in internal_fields or is_dependency or is_model:
                context_deps.append(name)
                continue
            
            p_description = f"Parameter {name}"
            p_required = param.default == inspect.Parameter.empty
            p_managed = None
            p_default_val = None
            
            if isinstance(param.default, params.Param):
                if param.default.description:
                    p_description = param.default.description
                if isinstance(param.default, params.Header):
                    if name.lower() in ["authorization", "x-api-key", "api-key", "token", "auth"]:
                        p_managed = "protocol"
                
                val = param.default.default
                try:
                    json.dumps(val)
                    p_default_val = val if val is not Ellipsis else None
                except:
                    p_default_val = None
                if val is Ellipsis or "PydanticUndefined" in str(val):
                    p_required = True
            else:
                val = param.default
                try:
                    json.dumps(val)
                    p_default_val = val if val is not Ellipsis else None
                except:
                    p_default_val = None
                if val is Ellipsis or "PydanticUndefined" in str(val):
                    p_required = True

            p_type, p_options = map_type(param.annotation)
            actual_parameters.append(ActionParam(
                name=name,
                description=p_description,
                type=p_type,
                required=p_required,
                managed_by=p_managed,
                options=p_options,
                default=p_default_val
            ))
            
        return actual_parameters, context_deps

    def _extract_response_schema(self, model: Any) -> Dict[str, Any]:
        if not model: return {}
        try:
            origin = getattr(model, "__origin__", None)
            args = getattr(model, "__args__", [])
            if origin in [list, List] and args:
                model = args[0]
            elif origin in [Union, Optional] and args:
                model = next((a for a in args if a != type(None)), model)

            if hasattr(model, "model_json_schema"):
                schema = model.model_json_schema()
                props = schema.get("properties", {})
                res = {}
                for k, v in props.items():
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

    def tool(self, 
             id: Optional[str] = None, 
             type: str = "read", 
             description: Optional[str] = None, 
             instructions: Optional[str] = None, 
             remedy: Optional[str] = None, 
             groups: Optional[List[str]] = None, 
             tags: Optional[List[str]] = None, 
             global_access: bool = False, 
             hidden: bool = False,
             opens_group: Optional[str] = None,
             parameters: Optional[List[ActionParam]] = None,
             headers: Optional[Dict[str, str]] = None,
             payload: Optional[Union[Dict[str, Any], List[ActionParam]]] = None,
             required_auth: Optional[str] = None,
             context_dependencies: Optional[List[str]] = None
            ):
        """Decorator to mark a FastAPI route as an ELEMM tool."""
        final_groups = list(set((groups or []) + (tags or [])))
        def decorator(func):
            action_id = id or func.__name__
            func._llm_landmark = {
                "id": action_id,
                "type": type,
                "description": description,
                "extra": {
                    "instructions": instructions,
                    "remedy": remedy,
                    "groups": final_groups,
                    "global_access": global_access,
                    "hidden": hidden,
                    "opens_group": opens_group,
                    "parameters": parameters,
                    "headers": headers,
                    "payload": payload,
                    "required_auth": required_auth,
                    "context_dependencies": context_dependencies
                }
            }
            # Pre-register so bind_to_app can find it
            self.register_action(
                handler=func,
                id=action_id,
                type=type,
                description=description or "No description provided.",
                groups=final_groups,
                instructions=instructions,
                remedy=remedy,
                global_access=global_access,
                hidden=hidden,
                opens_group=opens_group,
                parameters=parameters,
                headers=headers,
                payload=payload,
                required_auth=required_auth,
                context_dependencies=context_dependencies
            )
            return func
        return decorator

    def action(self, 
               id: Optional[str] = None, 
               type: str = "write", 
               description: Optional[str] = None, 
               instructions: Optional[str] = None, 
               remedy: Optional[str] = None, 
               groups: Optional[List[str]] = None, 
               tags: Optional[List[str]] = None, 
               global_access: bool = False, 
               hidden: bool = False,
               opens_group: Optional[str] = None,
               parameters: Optional[List[ActionParam]] = None,
               headers: Optional[Dict[str, str]] = None,
               payload: Optional[Union[Dict[str, Any], List[ActionParam]]] = None,
               required_auth: Optional[str] = None,
               context_dependencies: Optional[List[str]] = None
              ):
        """Decorator to mark a FastAPI route as an ELEMM action."""
        return self.tool(
            id, type, description, instructions, remedy, groups, tags, global_access, hidden,
            opens_group, parameters, headers, payload, required_auth, context_dependencies
        )



    async def call_action(self, action_id: str, arguments: Dict[str, Any]) -> tuple[Any, int]:
        """Executes a registered landmark action by calling its FastAPI route internally."""
        action = next((a for a in self.actions if a.id == action_id), None)
        if not action:
            raise ValueError(f"Action {action_id} not found.")

        # Copy arguments to avoid modifying the original dict
        params_to_use = (arguments or {}).copy()
        url = action.url
        
        if url is None:
            logger.error(f"CRITICAL: Action '{action_id}' has NO URL!")
            raise ValueError(f"Action {action_id} has no registered URL.")

        # Fill path parameters (e.g. /locations/{city}/offices)
        for k in list(params_to_use.keys()):
            placeholder = f"{{{k}}}"
            if placeholder in url:
                old_url = url
                url = url.replace(placeholder, str(params_to_use.pop(k)))
                if self.debug:
                    print(f"DEBUG: Replaced {placeholder} in URL. Old: {old_url}, New: {url}")

        # Determine host-key for header scoping
        from urllib.parse import urlparse
        parsed = urlparse(url)
        host_key = parsed.netloc if parsed.netloc else "elemm-internal"
        
        current_headers = session_headers.get().get(host_key, {})
        
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://elemm-internal") as client:
            method = (action.method or "POST").upper()
            
            # Route parameters based on method type
            kwargs = {"headers": current_headers}
            if method in ["GET", "DELETE"]:
                kwargs["params"] = params_to_use
            else:
                kwargs["json"] = params_to_use

            resp = await client.request(method, url, **kwargs)
            
            # Internal logging (Uvicorn-style) only if debug is enabled
            if self.debug:
                status_msg = "OK" if resp.status_code < 400 else "ERROR"
                uv_logger = logging.getLogger("uvicorn.error")
                target_logger = uv_logger if uv_logger.handlers else logger
                target_logger.info(f"INTERNAL: \"{method} {url} HTTP/1.1\" {resp.status_code} {status_msg}")

            try:
                result = resp.json()
            except:
                result = {"status": "ok", "message": resp.text}
            
            # Protocol Enrichment: Inject remedy for failed actions (>= 400)
            if resp.status_code >= 400 and isinstance(result, dict):
                if action.remedy:
                    result["remedy"] = action.remedy
                elif resp.status_code == 404:
                    # If the URL still contains placeholders, it means path parameters were missing
                    import re
                    placeholders = re.findall(r"\{(\w+)\}", url)
                    if placeholders:
                        result["remedy"] = f"Missing arguments: {', '.join(placeholders)}. Please provide required arguments."
                    else:
                        result["remedy"] = "Action not found or resource missing. Verify parameters and try again."
            
            return result, resp.status_code

Elemm = FastAPIProtocolManager
