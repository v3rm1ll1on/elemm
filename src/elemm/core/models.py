# Copyright (C) 2026 Marc Stöcker
# Website: https://elemm.dev
#
# This program is licensed under the Business Source License 1.1 (BSL 1.1).
# See the LICENSE file in the root directory for details.

from pydantic import BaseModel, ConfigDict, Field
from typing import List, Dict, Any, Optional, Callable, Union

class Parameter(BaseModel):
    """Definiert einen Eingabeparameter für eine Landmark."""
    name: str
    type: str = "string"
    description: str
    required: bool = True
    default: Optional[Any] = None
    options: Optional[Union[List[Any], Dict[str, Any]]] = None
    aliases: List[str] = Field(default_factory=list)
    location: str = "query" # query, path, header, body
    meta: Dict[str, Any] = Field(default_factory=dict)

class LandmarkMetadata(BaseModel):
    """Die rein deklarativen Metadaten aus der YAML."""
    description: str
    type: str = "navigation"  # action, tool, navigation
    instructions: Optional[str] = None
    remedy: Optional[str] = None
    parameters: Optional[List[Parameter]] = None
    returns: Optional[str] = None
    response_schema: Optional[Dict[str, Any]] = None
    tags: List[str] = Field(default_factory=list)
    groups: List[str] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)

class Landmark(LandmarkMetadata):
    """Die vollständige Landmark inklusive Runtime-Handler."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    id: str
    handler: Optional[Callable] = None
    tools: List["Landmark"] = Field(default_factory=list)

class LandmarkRegistry:
    """Interface für das Laden von Landmark-Metadaten."""
    def get(self, landmark_id: str) -> Optional[LandmarkMetadata]:
        raise NotImplementedError()

class Manifest(BaseModel):
    """Das generierte Protokoll-Manifest."""
    version: str = "2.0"
    welcome_message: Optional[str] = None
    instructions: str
    landmarks: List[Landmark]