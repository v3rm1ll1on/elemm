from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Union

class ActionParam(BaseModel):
    name: str
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

class AIProtocolManifest(BaseModel):
    version: str = "v1-lmlmm"
    agent_welcome: str
    protocol_instructions: Optional[str] = None
    openapi_url: Optional[str] = None
    current_group: Optional[str] = "root"
    navigation: List[Dict[str, Any]] = [] # Compact navigation landmarks
    actions: List[AIAction]
