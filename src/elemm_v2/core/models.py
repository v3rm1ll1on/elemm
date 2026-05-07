from pydantic import BaseModel, ConfigDict, Field
from typing import List, Dict, Any, Optional, Callable, Union

class Parameter(BaseModel):
    """Definiert einen Eingabeparameter für eine Landmark."""
    name: str
    type: str = "string"
    description: str
    required: bool = True
    default: Optional[Any] = None
    options: Optional[List[Any]] = None

class LandmarkMetadata(BaseModel):
    """Die rein deklarativen Metadaten aus der YAML."""
    description: str
    type: str = "action"  # action, tool, navigation
    instructions: Optional[str] = None
    remedy: Optional[str] = None
    parameters: Optional[List[Parameter]] = None
    response_schema: Optional[Dict[str, Any]] = None
    tags: List[str] = Field(default_factory=list)
    groups: List[str] = Field(default_factory=list)

class Landmark(LandmarkMetadata):
    """Die vollständige Landmark inklusive Runtime-Handler."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    id: str
    handler: Optional[Callable] = None
    tools: List["Landmark"] = Field(default_factory=list)

class Manifest(BaseModel):
    """Das generierte Protokoll-Manifest."""
    version: str = "2.0"
    welcome_message: Optional[str] = None
    instructions: str
    landmarks: List[Landmark]
