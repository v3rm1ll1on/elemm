import logging
from typing import Any, Dict, List, Optional, Callable
from pydantic import BaseModel
from .models import Landmark, LandmarkRegistry, Manifest, Parameter

logger = logging.getLogger(__name__)

class AIProtocolManager:
    """Zentrale für das Elemm v2 Protokoll (Back-to-Basics)."""
    
    DEFAULT_INSTRUCTIONS = """# ELEMM v2 PROTOCOL RULES
1. **DISCOVERY**: Use 'get_manifest' to see landmarks.
2. **INSPECTION**: Use 'inspect_landmark' for technical signatures.
3. **EXECUTION**: Use 'call_action' or 'execute_sequence' ONLY.
4. **MEMORY**: Use 'list_aliases' to see stored findings ($step_0, $step_1, etc.)
"""

    def __init__(self, registry: Optional[LandmarkRegistry] = None, presenter: Optional[Any] = None, **kwargs):
        # Fallback for benchmark which might not pass a registry
        if registry is None:
            from .models import LandmarkRegistry
            class DummyRegistry(LandmarkRegistry):
                def get(self, id): return None
            self.registry = DummyRegistry()
        else:
            self.registry = registry
            
        from .presenter import ManifestPresenter
        self.presenter = presenter or ManifestPresenter()
        self.landmarks: Dict[str, Landmark] = {}
        self.global_context: Dict[str, Any] = {}
        
        # Handle kwargs from benchmark
        self.instructions: str = kwargs.get("instructions", self.DEFAULT_INSTRUCTIONS)
        self.welcome_message: str = kwargs.get("welcome_message", "SOLARIS ENTERPRISE HUB (SECURED BY ELEMM v2)")
        self.version = kwargs.get("version", "2.2.0")
        self.ctx_threshold = kwargs.get("ctx_threshold", 2000)
        self.manifest_max_ctx = self.ctx_threshold
        
        from .repair import SmartRepairEngine
        self.repair = SmartRepairEngine()

    def landmark(self, landmark_id: str, **landmark_data):
        """Dekorator für Landmark-Tools."""
        def decorator(func: Callable):
            parts = landmark_id.split(":")
            
            # Fetch Metadata from Registry if available
            tool_meta = self.registry.get(landmark_id)
            desc = landmark_data.pop("description", None) or (tool_meta.description if tool_meta else None) or func.__doc__ or f"Tool: {landmark_id}"
            params = landmark_data.pop("parameters", None) or (tool_meta.parameters if tool_meta else [])
            
            if len(parts) > 1:
                root_id = parts[0]
                if root_id not in self.landmarks:
                    root_meta = self.registry.get(root_id)
                    self.landmarks[root_id] = Landmark(
                        id=root_id,
                        description=root_meta.description if root_meta else f"Area: {root_id}"
                    )
                
                tool = Landmark(id=landmark_id, handler=func, description=desc, parameters=params, **landmark_data)
                self.landmarks[root_id].tools.append(tool)
                self.landmarks[landmark_id] = tool
            else:
                self.landmarks[landmark_id] = Landmark(id=landmark_id, handler=func, description=desc, parameters=params, **landmark_data)
            
            return func
        return decorator

    async def call_action(self, action_id: str, arguments: Dict[str, Any]) -> Any:
        """Führt eine Action aus mit Smart Repair und Auto-Aliasing."""
        landmark = self.landmarks.get(action_id)
        
        # 1. Check Existence
        if not landmark:
            return self.repair.handle_missing_action(action_id, list(self.landmarks.keys())).dict()

        # 2. Check Callability (Area vs Tool)
        if not landmark.handler:
            if landmark.tools:
                return self.repair.handle_namespace_execution_attempt(action_id).dict()
            return {"status": "error", "message": f"Tool {action_id} has no implementation."}

        # 3. Validate Parameters
        missing = [p.name for p in (landmark.parameters or []) if p.required and p.name not in arguments]
        if missing:
            schema = {p.name: p.type for p in (landmark.parameters or [])}
            return self.repair.handle_invalid_params(action_id, missing, schema).dict()

        # 4. Execute
        try:
            import inspect
            sig = inspect.signature(landmark.handler)
            filtered_args = {k: v for k, v in arguments.items() if k in sig.parameters}
            
            logger.info(f"Executing {action_id} with {filtered_args}")
            
            if inspect.iscoroutinefunction(landmark.handler):
                result = await landmark.handler(**filtered_args)
            else:
                result = landmark.handler(**filtered_args)
            
            # Smart Remedy Injection: If the tool returns an error, enrich it with metadata remedies
            if isinstance(result, dict) and result.get("status") == "error":
                meta = self.registry.get(action_id)
                if meta and meta.remedy and "remedy" not in result:
                    result["remedy"] = meta.remedy
            
            # Auto-Aliasing
            self.global_context["last_result"] = result
            if isinstance(result, dict):
                self.global_context.update(result)
            
            return result
        except Exception as e:
            # Nur Warnung loggen statt vollem Traceback (vermeidet Konsolen-Spam bei validen Agenten-Fehlern)
            logger.warning(f"Execution failed for {action_id}: {e} | Args: {filtered_args}")
            
            # Versuche, saubere Fehlermeldungen aus FastAPI oder ElemmError zu extrahieren
            error_detail = getattr(e, "detail", str(e))
            
            response = {
                "status": "error", 
                "message": f"Execution failed: {error_detail}"
            }
            
            # Wenn die Landmark ein Remedy definiert hat, leiten wir den Agenten an!
            if landmark.remedy:
                response["remedy"] = landmark.remedy
                
            return response

    def get_landmarks(self) -> List[Landmark]:
        """Gibt alle Root-Landmarken zurück."""
        return [l for l in self.landmarks.values() if ":" not in l.id]

    def get_manifest(self, **kwargs) -> str:
        """Generiert das Manifest (High-Level Topology für Progressive Disclosure)."""
        all_landmarks = [l for l in self.landmarks.values() if ":" not in l.id]
        
        # In v2.2 (TypeScript/Progressive Disclosure Update) zeigen wir standardmäßig 
        # NIE die Signaturen im Root-Manifest, um Kontext zu sparen (Lazy Loading).
        # Außer, es wird explizit 'full=True' angefordert (z.B. durch Legacy-Routen).
        is_full = kwargs.get("full", False)
        hide_signatures = not is_full
        
        return self.presenter.present_manifest(
            all_landmarks, 
            instructions=self.instructions,
            welcome_message=self.welcome_message,
            hide_json=hide_signatures
        )

    def inspect_landmark(self, landmark_id: str) -> str:
        """Detaillierte Einsicht in eine Landmarke."""
        landmark = self.landmarks.get(landmark_id)
        if not landmark:
            return f"Landmark '{landmark_id}' not found."
        
        # Falls es ein Root ist, zeigen wir seine Tools
        targets = [landmark]
        if not landmark.handler and landmark.tools:
            targets = landmark.tools
            
        return self.presenter.present_manifest(
            targets,
            welcome_message=f"INSPECTION: {landmark_id}",
            hide_json=False # Inspection ALWAYS shows JSON
        )

    def list_aliases(self) -> Dict[str, Any]:
        return self.global_context

    def get_manifest_md(self, **kwargs) -> str:
        return self.get_manifest(**kwargs)

    def load_metadata(self, path: str):
        """Loads YAML metadata and updates existing landmarks."""
        from .registry import MetadataRegistry
        self.registry = MetadataRegistry(path)
        logger.info(f"Metadata loaded from {path}. Refreshing tool definitions...")
        
        # Refresh parameters for already registered landmarks
        for lm_id, landmark in self.landmarks.items():
            meta = self.registry.get(lm_id)
            if meta:
                landmark.description = meta.description or landmark.description
                landmark.parameters = meta.parameters or landmark.parameters
                landmark.remedy = meta.remedy or landmark.remedy

    def bind(self, landmark_id: str):
        """Decorator binding for legacy compatibility."""
        return self.landmark(landmark_id)
