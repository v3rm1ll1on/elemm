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

class AIAction(BaseModel):
    id: str
    type: str
    description: str
    instructions: Optional[str] = None
    method: str
    url: str
    parameters: Optional[List[ActionParam]] = None
    headers: Optional[Dict[str, str]] = None
    payload: Optional[Union[Dict[str, Any], List[ActionParam]]] = None
    required_auth: Optional[str] = None
    response_schema: Optional[Dict[str, Any]] = None
    hidden: bool = False

class AIProtocolManifest(BaseModel):
    version: str = "v1-lmlmm"
    agent_welcome: str
    protocol_instructions: Optional[str] = None
    openapi_url: Optional[str] = None
    actions: List[AIAction]
