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
    type: str = "action"  # action, tool, navigation
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
