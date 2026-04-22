from fastapi import APIRouter, FastAPI, params, Request, Body, Header
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from typing import List, Dict, Any, Optional, Union, Tuple
import logging
import httpx
import json
import inspect

from .base import BaseAIProtocolManager
from .models import ActionParam
from .discovery import map_type, resolve_refs
from .repair import agent_repair_handler
from .mcp_fastapi import bind_mcp_sse, run_mcp_stdio

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
        self.app_root_path = ""
        self.router = APIRouter()
        self._setup_well_known(self.router)
        self._setup_navigation_tool(self.router)

    def _setup_navigation_tool(self, router_or_app: Union[APIRouter, FastAPI]):
        @router_or_app.get("/.well-known/module-navigation", include_in_schema=False)
        @self.action(
            id="enter_module", 
            description="Enter a specific enterprise module (IT, HR, Finance, Remediation).",
            instructions="Use this to switch context and access module-specific tools.",
            global_access=True
        )
        async def enter_module(module_name: str):
            return {"status": "success", "message": f"Entering {module_name}..."}

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
            action_id: str = Body(..., embed=True),
            parameters: Dict[str, Any] = Body(default={}, embed=True),
            x_elemm_internal_key: Optional[str] = Header(None, alias="X-Elemm-Internal-Key")
        ):
            try:
                # We use the internal call_action which handles routing and auth
                result = await self.call_action(action_id, parameters)
                return result
            except Exception as e:
                logger.error(f"Protocol Execution Error: {e}")
                return JSONResponse(status_code=400, content={"error": str(e)})

        @router_or_app.get("/.well-known/elemm-manifest.md", include_in_schema=False)
        async def get_md_manifest(request: Request, landmark_id: Optional[str] = None):
            from .manifest import ManifestGenerator
            from fastapi import Response
            
            if landmark_id:
                # Filter tools for the specific landmark
                actions = []
                for a in self.actions:
                    groups = a.groups if hasattr(a, "groups") else a.get("groups", [])
                    if landmark_id in groups:
                        actions.append({
                            "id": a.id if hasattr(a, "id") else a.get("id"),
                            "description": a.description if hasattr(a, "description") else a.get("description", "")
                        })
                md_content = ManifestGenerator.generate_detailed_landmark(landmark_id, actions)
            else:
                md_content = ManifestGenerator.generate_markdown(
                    system_name=self.agent_welcome or "Solaris Hub",
                    instructions=self.protocol_instructions or "",
                    landmarks=self.navigation_landmarks or [],
                    tools=self.get_mcp_tools(),
                    include_technical_metadata=True
                )
            
            return Response(content=md_content, media_type="text/markdown")

    def bind_to_app(self, app: FastAPI):
        """Scans all routes in the FastAPI app and registers those marked with @landmark."""
        if hasattr(app, "_elemm_bound"):
            return
        app._elemm_bound = True
        
        self.app = app
        self.app_root_path = getattr(app, "root_path", "").rstrip("/")
        self._setup_well_known(app)

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
                    landmark_meta = getattr(route.endpoint, "_llm_landmark", None)
                    if landmark_meta:
                        self._register_from_route(route, landmark_meta)
                        count += 1
                        if self.debug:
                            logger.info(f"Landmark registered '{landmark_meta['id']}' -> {route.methods} {route.path}")
                except Exception as e:
                    logger.error(f"Failed to register landmark from route {route.path}: {e}")
        
        if self.debug:
            logger.info(f"Discovery complete. Total landmarks: {count}")

    def _register_navigation_landmarks(self, app: FastAPI, tags_meta: List[Dict[str, Any]]):
        known_tags = {tm.get("name") for tm in tags_meta if tm.get("name")}
        
        # Add tags from routes
        for route in app.routes:
            if isinstance(route, APIRoute) and route.tags:
                for tag in route.tags:
                    if tag not in known_tags:
                        tags_meta.append({"name": tag})
                        known_tags.add(tag)

        for tm in tags_meta:
            tag_name = tm.get("name")
            if not tag_name: continue
            
            try:
                tag_id = "".join(c for c in tag_name.lower().replace(" ", "_").replace("&", "and") if c.isalnum() or c == "_")
                
                guidance = {
                    "it infrastructure": "to access server logs, node management and infrastructure controls.",
                    "security ops": "to retrieve active incident tickets and security alerts.",
                    "human resources": "to search the personnel directory and verify employee identities.",
                    "finance and audit": "to audit transactions and verify financial integrity.",
                    "remediation": "to execute quarantine, restarts and fund recovery actions."
                }
                purpose = guidance.get(tag_name.lower(), f"to discover tools related to {tag_name}.")
                
                self.register_action(
                    id=f"explore_{tag_id}",
                    type="navigation",
                    description=f"Navigate to {tag_name} {purpose}",
                    instructions=f"Call this when your investigation requires access to {tag_name} specific capabilities.",
                    method="GET",
                    url=f"{self.app_root_path}/.well-known/llm-landmarks.json?group={tag_name}",
                    opens_group=tag_name,
                    groups=[] 
                )
            except Exception as e:
                logger.error(f"Failed to create navigation landmark for tag {tag_name}: {e}")

    def _register_from_route(self, route: APIRoute, meta: Dict[str, Any]):
        method = list(route.methods)[0] if route.methods else "GET"
        url = route.path
        
        description = (meta["description"] or route.endpoint.__doc__ or route.description or route.summary or "").strip()
        instructions = (meta.get("instructions") or route.endpoint.__doc__ or "").strip()

        payload = self._extract_payload(route, meta)
        actual_parameters, context_deps = self._extract_parameters(route, meta)

        extra = meta.get("extra", {})
        groups = extra.get("groups") or extra.get("group") or extra.get("tags") or (route.tags if route.tags else [])
        if isinstance(groups, str):
            groups = [groups]

        self.register_action(
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
            
            if name in internal_fields or is_dependency:
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

    async def call_action(self, action_id: str, arguments: Dict[str, Any]) -> Any:
        """Executes a registered landmark action by calling its FastAPI route internally."""
        action = next((a for a in self.actions if a.id == action_id), None)
        if not action:
            raise ValueError(f"Action {action_id} not found.")

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://elemm-internal") as client:
            method = action.method or "POST"
            url = action.url
            if method.upper() == "GET":
                resp = await client.get(url, params=arguments)
            else:
                resp = await client.post(url, json=arguments)
            try:
                return resp.json()
            except:
                return {"status": "ok", "message": resp.text}

Elemm = FastAPIProtocolManager
