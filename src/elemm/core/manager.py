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
        self.welcome_message: str = kwargs.get("welcome_message", "ELEMM v2 SECURE INTERFACE")
        self.version = kwargs.get("version", "2.2.0")
        self.ctx_threshold = kwargs.get("ctx_threshold", 2000)
        self.manifest_max_ctx = self.ctx_threshold
        
        from .repair import SmartRepairEngine
        self.repair = SmartRepairEngine()
        
        from .sequencer import SequenceEngine
        self.sequencer = SequenceEngine(self)

    def landmark(self, landmark_id: str, **landmark_data):
        """Dekorator für Landmark-Tools."""
        def decorator(func: Callable):
            parts = landmark_id.split(":")
            
            # Fetch Metadata from Registry if available
            tool_meta = self.registry.get(landmark_id)
            
            desc = landmark_data.pop("description", None) or (tool_meta.description if tool_meta else None) or func.__doc__ or f"Tool: {landmark_id}"
            params = landmark_data.pop("parameters", None) or (tool_meta.parameters if tool_meta else [])
            returns = landmark_data.pop("returns", None) or (tool_meta.returns if tool_meta else None)
            remedy = landmark_data.pop("remedy", None) or (tool_meta.remedy if tool_meta else None)
            instructions = landmark_data.pop("instructions", None) or (tool_meta.instructions if tool_meta else None)

            if len(parts) > 1:
                root_id = parts[0]
                if root_id not in self.landmarks:
                    root_meta = self.registry.get(root_id)
                    self.landmarks[root_id] = Landmark(
                        id=root_id,
                        description=root_meta.description if root_meta else f"Area: {root_id}"
                    )
                
                tool = Landmark(
                    id=landmark_id, 
                    handler=func, 
                    description=desc, 
                    parameters=params, 
                    returns=returns,
                    remedy=remedy,
                    instructions=instructions,
                    **landmark_data
                )
                self.landmarks[root_id].tools.append(tool)
                self.landmarks[landmark_id] = tool
            else:
                self.landmarks[landmark_id] = Landmark(
                    id=landmark_id, 
                    handler=func, 
                    description=desc, 
                    parameters=params, 
                    returns=returns,
                    remedy=remedy,
                    instructions=instructions,
                    **landmark_data
                )
            
            return func
        return decorator

    async def call_action(self, action_id: str, arguments: Dict[str, Any]) -> Any:
        """Führt eine Action aus mit Smart Repair und Auto-Aliasing."""
        landmark = self.landmarks.get(action_id)
        
        # 1. Check Existence
        if not landmark:
            return self.repair.handle_missing_action(action_id, list(self.landmarks.keys())).dict(exclude_none=True)

        # 2. Check Callability (Area vs Tool)
        if not landmark.handler:
            if landmark.tools:
                return self.repair.handle_namespace_execution_attempt(action_id).dict(exclude_none=True)
            return {"status": "error", "message": f"Tool {action_id} has no implementation."}

        # 3. Validate Parameters
        params = landmark.parameters or []
        
        # 3.1 Check Required Fields
        missing = [p.name for p in params if p.required and p.name not in arguments]
        if missing:
            schema = {p.name: p.type for p in params}
            return self.repair.handle_invalid_params(action_id, missing, schema, custom_remedy=landmark.remedy).dict(exclude_none=True)

        # 3.2 Validate Values and Types
        for p in params:
            if p.name in arguments:
                val = arguments[p.name]
                
                # 3.2.1 Type Check (Basic)
                if p.type == "number" and not isinstance(val, (int, float)):
                    try:
                        val = float(val) # Try to auto-cast if it's a string number
                    except:
                        return {
                            "status": "error",
                            "message": f"Type mismatch for '{p.name}': Expected number, got {type(val).__name__}.",
                            "remedy": f"Please provide a numeric value (int or float) for '{p.name}'."
                        }

                # 3.2.2 Check Valid Options (Enum) with Fuzzy Matching
                if p.options and val not in p.options:
                    return self.repair.handle_invalid_value(p.name, val, p.options).dict(exclude_none=True)

        # Pre-execution placeholder check
        for k, v in arguments.items():
            if isinstance(v, str) and (v.upper() in ["UNKNOWN", "PLACEHOLDER", "UNKNOWN_TOKEN"] or v.startswith("$")):
                from .repair import SmartRepairEngine
                return SmartRepairEngine.handle_placeholder_detected(k, v).dict(exclude_none=True)

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
            
            # Smart Remedy Shadowing: Keep AI context clean
            if isinstance(result, dict) and result.get("status") == "error":
                meta = self.registry.get(action_id)
                if meta and meta.remedy:
                    logger.warning(f"Tool Error shadowed by Remedy: {result.get('message')}")
                    original_msg = result.get("message", "Unknown error")
                    result["message"] = f"{original_msg} | Remedy: {meta.remedy}"
                    # Remove raw error fields to prevent AI confusion
                    result.pop("technical_details", None)
                    result.pop("remedy", None) # It's now the main message
                
            # Auto-Aliasing: In v2 we only pipe via explicit aliases ($step0 etc.)
            # or the global_context which is managed by the sequencer/broker.
            # We no longer flatten results into the global namespace to avoid collisions.
            return result
        except Exception as e:
            # Extract clean error message
            error_detail = getattr(e, "detail", str(e))
            logger.warning(f"Execution failed for {action_id}: {error_detail} | Args: {filtered_args}")
            
            response = {
                "status": "error", 
                "message": f"Execution failed: {error_detail}"
            }
            
            # Apply Remedy Shadowing if available
            meta = self.registry.get(action_id)
            if meta and meta.remedy:
                logger.info(f"Shadowing exception for {action_id} with YAML remedy.")
                response["message"] = meta.remedy
                # Keep the technical info hidden from the primary message
                # but we could put it in a separate field if we really wanted to.
                # Per previous decision: We hide it from the AI.
                
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
            hide_json=hide_signatures,
            technical=kwargs.get("technical", False)
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
