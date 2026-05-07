import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Union
from .models import LandmarkMetadata

class MetadataRegistry:
    """Loads and manages declarative metadata for landmarks."""
    
    def __init__(self):
        self._storage: Dict[str, LandmarkMetadata] = {}

    def load_from_yaml(self, path: Union[str, Path]):
        """Loads metadata from a YAML file."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Metadata file not found: {p}")
            
        with open(p, 'r') as f:
            data = yaml.safe_load(f)
            
        if not data or 'landmarks' not in data:
            return

        for action_id, meta in data['landmarks'].items():
            self._storage[action_id] = LandmarkMetadata(**meta)

    def add(self, action_id: str, description: str, remedy: Optional[str] = None):
        """Adds metadata manually."""
        self._storage[action_id] = LandmarkMetadata(description=description, remedy=remedy)

    def get(self, action_id: str) -> Optional[LandmarkMetadata]:
        """Returns the metadata for an ID."""
        return self._storage.get(action_id)

