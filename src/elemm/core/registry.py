import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Union, List
from .models import LandmarkMetadata, LandmarkRegistry, Parameter

class MetadataRegistry(LandmarkRegistry):
    """Loads and manages declarative metadata for landmarks."""
    
    def __init__(self, path: Optional[Union[str, Path]] = None):
        self._storage: Dict[str, LandmarkMetadata] = {}
        self.global_aliases: Dict[str, List[str]] = {}
        if path:
            self.load_from_yaml(path)

    def load_from_yaml(self, path: Union[str, Path]):
        """Loads metadata from a YAML file."""
        p = Path(path)
        if not p.exists():
            return
            
        with open(p, 'r') as f:
            data = yaml.safe_load(f)
            
        if not data:
            return

        # Load Global Aliases
        self.global_aliases = data.get("global_aliases", {})
        
        if 'landmarks' not in data:
            return

        landmarks_data = data['landmarks']
        
        if isinstance(landmarks_data, list):
            for item in landmarks_data:
                lm_id = item.get("id")
                if not lm_id: continue
                
                # Handle tools
                if "tools" in item:
                    for t in item["tools"]:
                        t_id = t.get("id")
                        if not t_id: continue
                        full_id = f"{lm_id}:{t_id}" if ":" not in t_id else t_id
                        self._process_meta(full_id, t)
                
                self._process_meta(lm_id, item)
        else:
            for action_id, meta in landmarks_data.items():
                self._process_meta(action_id, meta)

    def _process_meta(self, action_id: str, meta: Dict[str, Any]):
        raw_params = meta.get("parameters", [])
        params = []
        for rp in raw_params:
            params.append(Parameter(**rp))
        
        meta_copy = meta.copy()
        meta_copy["parameters"] = params
        # Avoid passing 'id' to LandmarkMetadata if it doesn't want it (it usually doesn't)
        self._storage[action_id] = LandmarkMetadata(**{k: v for k, v in meta_copy.items() if k != "id" and k != "tools"})

    def get_synonyms(self, param_name: str, tool_id: str = None) -> List[str]:
        """Returns all potential synonyms for a parameter name."""
        synonyms = set()
        
        # 1. Global Aliases
        if param_name in self.global_aliases:
            synonyms.update(self.global_aliases[param_name])
            
        # 2. Tool-Specific Aliases
        if tool_id:
            meta = self.get(tool_id)
            if meta and meta.parameters:
                param = next((p for p in meta.parameters if p.name == param_name), None)
                if param and param.aliases:
                    synonyms.update(param.aliases)
                    
        return list(synonyms)

    def get(self, action_id: str) -> Optional[LandmarkMetadata]:
        """Returns the metadata for an ID."""
        return self._storage.get(action_id)
