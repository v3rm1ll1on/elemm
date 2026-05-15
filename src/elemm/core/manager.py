# Copyright (C) 2026 Marc Stöcker
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import logging
from typing import Any, Dict, List, Optional, Callable, Union
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
        self.version = kwargs.get("version", "1.0.0")
        self.ctx_threshold = kwargs.get("ctx_threshold", 2000)
        self.manifest_max_ctx = self.ctx_threshold
        
        from .repair import SmartRepairEngine
        self.repair = SmartRepairEngine()
        
        from .sequencer import SequenceEngine
        self.sequencer = SequenceEngine(self)

        from .discovery import ParameterDiscovery
        self.discovery = ParameterDiscovery()

    def landmark(self, landmark_id: str, **landmark_data):
        """Dekorator für Landmark-Tools."""
        def decorator(func: Optional[Callable]):
            actual_id = landmark_id
            if func and hasattr(func, "__name__") and ":" not in actual_id:
                actual_id = f"{landmark_id}:{func.__name__}"
            
            parts = actual_id.split(":")
            
            # Metadata
            tool_meta = self.registry.get(actual_id)
            desc = landmark_data.pop("description", None) or (tool_meta.description if tool_meta else None) or (func.__doc__ if func else None) or f"Area: {actual_id}"
            params = landmark_data.pop("parameters", None) or (tool_meta.parameters if tool_meta else None)
            if params is None and func:
                params = self.discovery.extract_parameters(func)
                
            returns = landmark_data.pop("returns", None) or (tool_meta.returns if tool_meta else None)
            remedy = landmark_data.pop("remedy", None) or (tool_meta.remedy if tool_meta else None)
            instructions = landmark_data.pop("instructions", None) or (tool_meta.instructions if tool_meta else None)

            # Build Hierarchy
            for i in range(1, len(parts) + 1):
                current_id = ":".join(parts[:i])
                is_leaf = (i == len(parts))
                
                if current_id not in self.landmarks:
                    meta = self.registry.get(current_id)
                    m_data = meta.model_dump(exclude_none=True) if meta else {}
                    self.landmarks[current_id] = Landmark(
                        id=current_id,
                        description=m_data.get("description", f"Area: {current_id}"),
                        **{k: v for k, v in m_data.items() if k != "id" and k != "description"}
                    )

                if is_leaf:
                    lm = self.landmarks[current_id]
                    lm.handler = func
                    lm.description = desc
                    lm.parameters = params
                    lm.returns = returns
                    lm.remedy = remedy
                    lm.instructions = instructions
                    for k, v in landmark_data.items():
                        setattr(lm, k, v)

                if i > 1:
                    parent_id = ":".join(parts[:i-1])
                    parent = self.landmarks[parent_id]
                    current = self.landmarks[current_id]
                    if not any(t.id == current_id for t in parent.tools):
                        parent.tools.append(current)
            
            return func
        return decorator

    # Backward compatibility alias
    bind = landmark

    def register(self, landmark_id: str, **landmark_data):
        """Hilfsmethode zur Registrierung von Landmarken ohne Handler."""
        return self.landmark(landmark_id, **landmark_data)(None)

    async def call_action(self, action_id: str, arguments: Dict[str, Any]) -> Any:
        """Führt eine Action aus mit Smart Repair und Auto-Aliasing."""
        landmark = self.landmarks.get(action_id)
        
        # 1. Check Existence
        if not landmark:
            return self.repair.handle_missing_action(action_id, list(self.landmarks.keys())).model_dump(exclude_none=True)

        # 2. Check Callability (Area vs Tool)
        if not landmark.handler:
            if landmark.tools:
                return self.repair.handle_namespace_execution_attempt(action_id).model_dump(exclude_none=True)
            return {"status": "error", "message": f"Tool {action_id} has no implementation."}

        # 3. Validate Parameters
        params = landmark.parameters or []
        
        # 3.1 Check Required Fields
        missing = [p.name for p in params if p.required and p.name not in arguments]
        if missing:
            schema = {p.name: p.type for p in params}
            return self.repair.handle_invalid_params(action_id, missing, schema, custom_remedy=landmark.remedy).model_dump(exclude_none=True)

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
                    return self.repair.handle_invalid_value(p.name, val, p.options).model_dump(exclude_none=True)

        # Pre-execution placeholder check
        for k, v in arguments.items():
            if isinstance(v, str) and (v.upper() in ["UNKNOWN", "PLACEHOLDER", "UNKNOWN_TOKEN"] or v.startswith("$")):
                from .repair import SmartRepairEngine
                return SmartRepairEngine.handle_placeholder_detected(k, v).dict(exclude_none=True)

        # 4. Execute
        try:
            import inspect
            sig = inspect.signature(landmark.handler)
            sig_params = [p for n, p in sig.parameters.items() if n not in ["self", "cls", "context", "kwargs"]]
            
            # --- SMART WRAPPING ---
            # If the handler expects a single Pydantic model, wrap the arguments
            final_args = arguments
            if len(sig_params) == 1:
                param = sig_params[0]
                try:
                    from pydantic import BaseModel
                    if inspect.isclass(param.annotation) and issubclass(param.annotation, BaseModel):
                        # Construct the model from arguments
                        model_inst = param.annotation(**arguments)
                        final_args = {param.name: model_inst}
                except Exception as e:
                    logger.debug(f"Pydantic wrapping failed for {action_id}: {e}")
            
            filtered_args = {k: v for k, v in final_args.items() if k in sig.parameters}
            
            logger.info(f"Executing {action_id} with {filtered_args}")
            
            if inspect.iscoroutinefunction(landmark.handler):
                result = await landmark.handler(**filtered_args)
            else:
                result = landmark.handler(**filtered_args)
            
            # Smart Remedy Shadowing: Keep AI context clean
            if isinstance(result, dict) and result.get("status") == "error":
                # Check Tool Remedy -> then Parent Landmark Remedy -> then Registry
                remedy = landmark.remedy
                
                # If tool has no remedy, check parent landmark
                if not remedy and ":" in action_id:
                    parent_id = action_id.split(":")[0]
                    parent = self.landmarks.get(parent_id)
                    if parent:
                        remedy = parent.remedy
                
                # Fallback to registry
                if not remedy:
                    meta = self.registry.get(action_id)
                    remedy = meta.remedy if meta else None
                
                if remedy and "remedy" not in result:
                    result["remedy"] = remedy
            
            # --- PROTOCOL HYGIENE ---
            try:
                from elemm_gateway.services.hygiene import ResponseSquisher
                select = arguments.get("_select")
                filter_str = arguments.get("_filter")
                limit = arguments.get("_limit")
                offset = arguments.get("_offset")
                
                if limit is not None: limit = int(limit)
                if offset is not None: offset = int(offset)
                
                if any(v is not None for v in [select, filter_str, limit, offset]) and result is not None:
                    # Convert to dict if it's a Pydantic model or dataclass
                    if hasattr(result, "model_dump"):
                        result = result.model_dump(exclude_none=True)
                    elif hasattr(result, "dict"):
                        result = result.dict()
                        
                    # Squish operates on dicts and lists safely
                    squished_data, was_truncated, total = ResponseSquisher.squish(result, select, filter_str, limit, offset)
                    
                    if was_truncated:
                        return {
                            "status": "success",
                            "data": squished_data,
                            "_HYGIENE_NOTICE": f"Output truncated for context hygiene. Showing {len(squished_data) if isinstance(squished_data, list) else 'partial'} of {total} items.",
                            "remedy": f"The result is large. Use '_offset={int(offset or 0) + (len(squished_data) if isinstance(squished_data, list) else 0)}' to fetch the next page of results."
                        }
                    result = squished_data
            except ImportError:
                pass

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

    def _get_registry_lower(self) -> Dict[str, Landmark]:
        """Lazy-loaded lower-case registry for fast lookups."""
        if not hasattr(self, "_registry_cache") or len(self._registry_cache) != len(self.landmarks):
            self._registry_cache = {k.lower(): v for k, v in self.landmarks.items()}
        return self._registry_cache

    def get_manifest(self, landmark_id: Optional[Union[str, List[str]]] = None, **kwargs) -> str:
        """Generiert ein dynamisches Manifest basierend auf dem Kontext (Case-Insensitive)."""
        all_landmarks = []
        logger.info(f"get_manifest called with landmark_id={landmark_id}")
        
        show_technical = kwargs.pop("technical", False)
        
        if landmark_id:
            ids = [landmark_id] if isinstance(landmark_id, str) else landmark_id
            reg_lower = self._get_registry_lower()
            
            for lid in ids:
                # Suche erst exakt, dann lower
                landmark = self.landmarks.get(lid) or reg_lower.get(lid.lower())
                
                if not landmark:
                    logger.warning(f"Landmark {lid} not found in registry.")
                    continue
                
                # Wenn es eine Area ist (kein handler), zeigen wir ihre Kinder
                if not getattr(landmark, 'handler', None) and landmark.tools:
                    logger.info(f"Expanding area {landmark.id} into {len(landmark.tools)} sub-items")
                    all_landmarks.extend(landmark.tools)
                else:
                    # Es ist ein Tool oder eine leere Area
                    all_landmarks.append(landmark)
        else:
            # Root-Ebene: Zeige alle Landmarks ohne Doppelpunkt (Distrikte/Hauptbereiche)
            all_landmarks = [l for l in self.landmarks.values() if ":" not in l.id]

    def get_manifest(self, landmark_ids: List[str] = None, technical: bool = False, **kwargs) -> str:
        """Generiert ein Markdown-Manifest für die angeforderten Landmarks."""
        lms = []
        if landmark_ids is None:
            # Root discovery: Show only high-level categories
            lms = [lm for lid, lm in self.landmarks.items() if ":" not in lid]
        else:
            for lid in landmark_ids:
                lm = self.landmarks.get(lid)
                if lm:
                    lms.append(lm)
        
        # Context-Hygiene: Header nur zeigen, wenn wir auf Root-Ebene sind
        is_root = landmark_ids is None
        
        return self.presenter.present_manifest(
            lms, 
            instructions=self.instructions if is_root else "",
            welcome_message=self.welcome_message if is_root else "",
            show_technical=technical,
            is_root=is_root,
            output_format=kwargs.pop("output_format", "markdown"),
            **kwargs
        )

    def search_landmarks(self, query: Union[str, List[str]], technical: bool = False, **kwargs) -> str:
        """Durchsucht alle Landmarks nach einem oder mehreren Suchbegriffen."""
        import re
        queries = [query] if isinstance(query, str) else query
        
        patterns = []
        for q in queries:
            try:
                patterns.append(re.compile(q, re.IGNORECASE))
            except re.error:
                patterns.append(re.compile(re.escape(q), re.IGNORECASE))

        matches_set = set()
        matches = []
        
        for lid, lm in self.landmarks.items():
            for pattern in patterns:
                if pattern.search(lid) or (lm.description and pattern.search(lm.description)):
                    if lid not in matches_set:
                        matches_set.add(lid)
                        matches.append(lm)
                    break # One match is enough
        
        return self.presenter.present_manifest(
            matches,
            instructions=f"# SEARCH RESULTS FOR: {queries}",
            show_technical=technical,
            output_format=kwargs.pop("output_format", "markdown"),
            **kwargs
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

    def get_manifest_dict(self) -> List[Dict[str, Any]]:
        """Gibt eine Liste aller Landmarken als Dictionary zurück."""
        return [l.model_dump(exclude_none=True) for l in self.landmarks.values()]


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



class ElemmGateway:
    """
    High-level entry point for the Landmark Manifest Protocol.
    
    This class wraps AIProtocolManager and provides a convenient API for
    defining actions and running gateway servers (FastAPI or MCP).
    """

    def __init__(self, name: str = "ElemmGateway", instructions: Optional[str] = None):
        self.manager = AIProtocolManager(instructions=instructions, welcome_message=f"{name} SECURE INTERFACE")
        self.name = name

    def configure_landmark(self, landmark: str, **kwargs):
        """
        Configure metadata for a specific landmark (namespace).
        Example: gateway.configure_landmark("Security", priority=1, description="...")
        """
        lm = self.manager.get_or_create_landmark(landmark)
        for k, v in kwargs.items():
            if hasattr(lm, k):
                setattr(lm, k, v)
        logger.info(f"Configured landmark {landmark}")

    def action(self, landmark: str, **kwargs):
        """
        Decorator to register a function as an Elemm Action.
        
        Args:
            landmark: The landmark ID (namespace:tool_name).
            **kwargs: Metadata like 'description', 'remedy', etc.
        """
        return self.manager.landmark(landmark, **kwargs)

    def run(self, host: str = "0.0.0.0", port: int = 8000):
        """Starts a FastAPI gateway server."""
        import uvicorn
        from fastapi import FastAPI
        from ..gateways.fastapi import FastAPIGateway
        
        app = FastAPI(title=self.name)
        gateway = FastAPIGateway(self.manager)
        gateway.bind_to_app(app)
        
        # print(f"Elemm: Landmark Manifest Protocol active at http://{host}:{port}")
        uvicorn.run(app, host=host, port=port)

    def run_mcp(self):
        """Starts an MCP gateway server via STDIO."""
        from ..gateways.mcp_server import MCPGateway
        gateway = MCPGateway(self.manager, server_name=self.name)
        gateway.run_stdio()

    def load_metadata(self, path: str):
        """Loads additional YAML metadata."""
        self.manager.load_metadata(path)
