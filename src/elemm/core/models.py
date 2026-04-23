# This file is part of Elemm.
#
# Elemm is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Elemm is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Elemm.  If not, see <https://www.gnu.org/licenses/>.

from pydantic import BaseModel, ConfigDict
from typing import List, Dict, Any, Optional, Union, Callable

class ActionParam(BaseModel):
    name: Optional[str] = None
    description: str
    type: str = "string"
    required: bool = False
    default: Optional[Any] = None
    example: Optional[Any] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    options: Optional[List[Any]] = None
    managed_by: Optional[str] = None # e.g., "protocol", "user", "environment"

class AIAction(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    id: str
    type: str
    description: str
    instructions: Optional[str] = None
    remedy: Optional[str] = None
    groups: List[str] = []
    opens_group: Optional[str] = None
    global_access: bool = False
    method: Optional[str] = None
    url: Optional[str] = None
    tags: List[str] = ["default"]
    parameters: Optional[List[ActionParam]] = None
    headers: Optional[Dict[str, str]] = None
    payload: Optional[Union[Dict[str, Any], List[ActionParam]]] = None
    required_auth: Optional[str] = None
    context_dependencies: Optional[List[str]] = None
    response_schema: Optional[Dict[str, Any]] = None
    hidden: bool = False
    handler: Optional[Callable] = None

class AIProtocolManifest(BaseModel):
    version: str = "v1-lmlmm"
    agent_welcome: str
    protocol_instructions: Optional[str] = None
    openapi_url: Optional[str] = None
    current_group: Optional[str] = "root"
    navigation: List[Dict[str, Any]] = [] # Compact navigation landmarks
    actions: List[AIAction]
