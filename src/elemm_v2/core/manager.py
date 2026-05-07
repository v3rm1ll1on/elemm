from typing import Callable, Optional, List, Dict, Any
from .models import Landmark, Manifest, LandmarkMetadata
from .registry import MetadataRegistry
from .presenter import ManifestPresenter
import logging

logger = logging.getLogger(__name__)

class AIProtocolManager:
    """Verwaltet die Bindung zwischen Code und Protokoll-Spezifikation."""

    DEFAULT_INSTRUCTIONS = """# ELEMM v2 DYNAMIC PROTOCOL
1. **DISCOVERY**: `get_manifest` for tools.
2. **EXECUTION**: `execute_sequence` for chaining.

### 🔗 PIPING
Chain results via `$ALIAS.field`. 
Example: If step 0 has `alias: "res0"`, use `"$res0.id"` in step 1.
"""
    def __init__(self, instructions: str, version: str = "2.0", hybrid_threshold: int = 10, navigation_landmarks: Optional[List[Dict[str, Any]]] = None):
        self.instructions = instructions
        self.version = version
        self.registry = MetadataRegistry()
        self.presenter = ManifestPresenter()
        self.landmarks: Dict[str, Landmark] = {}
        self.welcome_message: Optional[str] = None
        self.hybrid_threshold = hybrid_threshold
        self.navigation_landmarks = navigation_landmarks or []

    def load_metadata(self, path: str):
        """Loads the YAML specification."""
        self.registry.load_from_yaml(path)

    def bind(self, landmark_id: str):
        """Dekorator, um eine Funktion an eine Landmark-ID zu binden (hierarchisch & angereichert)."""
        def decorator(func: Callable):
            parts = landmark_id.split(":")
            
            # 1. Metadaten-Extraktion
            meta = self.registry.get(landmark_id)
            has_explicit_meta = meta is not None
            if not meta:
                from .models import LandmarkMetadata
                meta = LandmarkMetadata(description="") # Leer lassen für Fallback
            
            landmark_data = meta.model_dump()
            
            # v1 Pattern: Automatische Parameter-Extraktion
            if not landmark_data.get("parameters"):
                import inspect
                from .models import Parameter
                from .discovery import TypeMapper
                sig = inspect.signature(func)
                params = []
                for name, param in sig.parameters.items():
                    if name in ["self", "cls"]: continue
                    p_type, p_options = TypeMapper.map_type(param.annotation)
                    params.append(Parameter(name=name, type=p_type, options=p_options, description=f"Parameter {name}", required=param.default == inspect.Parameter.empty))
                landmark_data["parameters"] = params

            # v2 New: Response Schema Inference (Pydantic Magic)
            from typing import get_type_hints
            try:
                hints = get_type_hints(func)
                return_hint = hints.get('return')
                if return_hint:
                    from .discovery import TypeMapper
                    p_type, p_schema = TypeMapper.map_type(return_hint)
                    landmark_data["response_schema"] = p_schema if p_type == "object" else {"type": p_type}
            except:
                pass

            # v1 Pattern: Description Enrichment (The "Secret Sauce")
            instructions = landmark_data.get("instructions")
            remedy = landmark_data.get("remedy")
            
            # Priorität: 1. Explizite Meta-Beschreibung, 2. Docstring, 3. Fallback
            base_desc = (meta.description if has_explicit_meta and meta.description else None) or func.__doc__ or f"Action {landmark_id}"
            
            enriched_desc = ""
            if instructions: enriched_desc += f"INSTRUCTIONS: {instructions}\n"
            enriched_desc += base_desc
            
            # Piping Metadata
            res_schema = landmark_data.get("response_schema")
            if res_schema:
                props = []
                if res_schema.get("type") == "object":
                    props = list(res_schema.get("properties", {}).keys())
                elif res_schema.get("type") == "array" and "items" in res_schema:
                    props = list(res_schema.get("items", {}).get("properties", {}).keys())
                
                if props:
                    enriched_desc += f"\n\nPIPING: Returns {', '.join(props)}. Use '$ALIAS.field' to chain (replace ALIAS with your step name)."

            if remedy: enriched_desc += f"\n\nIMPORTANT: {remedy}"
            
            landmark_data["description"] = enriched_desc.strip()

            # 2. Hierarchische Zuordnung
            if len(parts) > 1:
                root_id = parts[0]
                if root_id not in self.landmarks:
                    root_meta = self.registry.get(root_id)
                    self.landmarks[root_id] = Landmark(
                        id=root_id,
                        description=root_meta.description if root_meta else f"Navigate to {root_id}"
                    )
                
                tool = Landmark(id=landmark_id, handler=func, **landmark_data)
                self.landmarks[root_id].tools.append(tool)
                self.landmarks[landmark_id] = tool
            else:
                self.landmarks[landmark_id] = Landmark(id=landmark_id, handler=func, **landmark_data)
            
            return func
        return decorator

    async def call_action(self, action_id: str, arguments: Dict[str, Any]) -> Any:
        """Executes a registered action."""
        from .context import landmark_ctx
        landmark = self.landmarks.get(action_id)
        
        # v1 Compatibility: Try short ID if full ID not found
        if not landmark:
            short_matches = [l for l in self.landmarks.values() if l.id.split(":")[-1] == action_id]
            if len(short_matches) == 1:
                landmark = short_matches[0]
                action_id = landmark.id
            elif len(short_matches) > 1:
                return {
                    "status": "error",
                    "message": f"Ambiguous short ID '{action_id}'. Matches: {[m.id for m in short_matches]}",
                    "remedy": "Use the full 'landmark:action' ID."
                }
        
        if not landmark:
            return {
                "status": "error", 
                "message": f"Action '{action_id}' not found. Check the manifest.",
                "remedy": "Use 'get_manifest' to see available actions."
            }
        
        if not landmark.handler:
            # Check if this is a root landmark (area) with tools
            if landmark.tools:
                tool_ids = [t.id for t in landmark.tools]
                return {
                    "status": "error",
                    "message": f"'{action_id}' is an area, not a callable tool.",
                    "remedy": f"Available tools in this area: {tool_ids}. Use 'call_action(action=\"ID\", parameters={{...}})' or 'execute_sequence'."
                }
            return {
                "status": "error",
                "message": f"Action '{action_id}' has no implementation.",
                "remedy": "Ensure you are using the correct Action ID from the manifest."
            }
        token = landmark_ctx.set(action_id)
        
        try:
            import inspect
            sig = inspect.signature(landmark.handler)
            
            noise_warning = ""
            if landmark.parameters:
                allowed = {p.name for p in landmark.parameters}
                spurious = set(arguments.keys()) - allowed
                if spurious:
                    noise_warning = f" (Ignored invalid parameters: {', '.join(spurious)})"
            
            filtered_args = {k: v for k, v in arguments.items() if k in sig.parameters}
            
            # Small Model Defense: Halluzinierte Präfixe (z.B. q='q=value') entfernen
            sanitized_args = {}
            for k, v in filtered_args.items():
                if isinstance(v, str) and v.startswith(f"{k}="):
                    sanitized_args[k] = v[len(k)+1:]
                else:
                    sanitized_args[k] = v
            
            if inspect.iscoroutinefunction(landmark.handler):
                result = await landmark.handler(**sanitized_args)
            else:
                result = landmark.handler(**sanitized_args)
            
            # Noise Filtering
            if isinstance(result, dict):
                pass # No core noise filtering (let the client handle it)
            
            return result
        except Exception as e:
            from .exceptions import ElemmError
            error_msg = str(e)
            
            # Detailed error extraction for FastAPI/Starlette exceptions
            detail = getattr(e, "detail", None)
            status_code = getattr(e, "status_code", 400)
            
            if detail:
                if isinstance(detail, list):
                    missing = [item.get("loc", ["?"])[-1] for item in detail if item.get("type") == "missing"]
                    if missing:
                        error_msg = f"Missing required parameters: {', '.join(missing)}"
                else:
                    error_msg = str(detail)
            elif status_code == 422:
                remedy = self.metadata_registry.get_tool_metadata(action_id).get("remedy")
                error_msg = "Error: 422: Unprocessable Entity"
                if remedy:
                    error_msg += f". REMEDY: {remedy}"
                else:
                    error_msg += " (Validation failed or lookup returned no results)"

            # Remedy lookup
            remedy = landmark.remedy if landmark else None
            
            # Auto-remedy for missing parameters
            if not remedy and "Missing required parameters" in error_msg:
                req_params = [p.name for p in (landmark.parameters or []) if p.required]
                if req_params:
                    remedy = f"Required: {req_params}. Use 'inspect_landmark(\"{action_id}\")' for full signature."

            final_msg = f"Error: {status_code}: {error_msg}"
            if remedy:
                final_msg += f". REMEDY: {remedy}"
            
            return {"status": "error", "message": final_msg}
        finally:
            landmark_ctx.reset(token)

    def bind_to_app(self, app: Any):
        """Scans a FastAPI app and automatically registers all routes as landmarks (v1 style)."""
        from fastapi.routing import APIRoute
        
        for route in app.routes:
            if not isinstance(route, APIRoute): continue
            if route.path.startswith("/.well-known"): continue
            
            # ID generieren (Tag:Name oder einfach Name)
            tag = route.tags[0] if route.tags else None
            landmark_id = f"{tag}:{route.name}" if tag else route.name
            
            # Falls schon manuell gebunden, überspringen
            if landmark_id in self.landmarks: continue
            
            # Metadaten aus Route extrahieren
            description = route.description or route.summary or route.endpoint.__doc__ or f"Action {route.name}"
            
            # Wir nutzen die bestehende bind Logik, indem wir den Decorator manuell aufrufen
            binder = self.bind(landmark_id)
            binder(route.endpoint)
            
            logger.info(f"Auto-registered landmark: {landmark_id}")

    def get_landmarks(self, flatten: Optional[bool] = None) -> List[Landmark]:
        """Returns landmarks. If 'flatten=True' or few tools are present, hierarchy is resolved."""
        all_lms = sorted(list(self.landmarks.values()), key=lambda x: x.id)
        
        # Nur sichtbare (nicht-noise) Landmarks für den Threshold zählen
        visible_lms = all_lms
        
        # v1 Genius: Auto-Flattening wenn wenig los ist
        if flatten is True or (flatten is None and len(visible_lms) <= self.hybrid_threshold):
            return visible_lms
            
        # Standard: Nur Roots zeigen
        return [lm for lm in all_lms if ":" not in lm.id]

    def get_manifest_md(self, full: bool = False, technical: bool = False, navigation_ids: Optional[List[str]] = None) -> str:
        """Returns the manifest in Markdown format (SMART/Hybrid style)."""
        lms = self.get_landmarks()
        instr = self.instructions or self.DEFAULT_INSTRUCTIONS
        # IDs für essenzielle Landmarks extrahieren
        nav_ids = navigation_ids or [str(l.get("id") if isinstance(l, dict) else getattr(l, "id", "")) for l in self.navigation_landmarks]
        
        return self.presenter.present_manifest(
            lms, 
            welcome_message=self.welcome_message, 
            instructions=instr,
            full=full,
            technical=technical,
            navigation_ids=nav_ids
        )

    def get_manifest_object(self) -> Manifest:
        """Returns the Pydantic model of the manifest."""
        return Manifest(
            version=self.version,
            welcome_message=self.welcome_message,
            instructions=self.instructions,
            landmarks=list(self.landmarks.values())
        )

    def get_manifest_dict(self) -> Dict[str, Any]:
        """Returns the serialized manifest dict (JSON-compatible)."""
        manifest = self.get_manifest_object()
        return manifest.model_dump(exclude_none=True, exclude={"landmarks": {"__all__": {"handler"}}})
