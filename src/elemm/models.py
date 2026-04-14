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
    protocol_instructions: str = (
        "You are an autonomous web agent. This manifest defines 'actions' you can call like functions. "
        "DECISION RULES: "
        "1. The 'parameters' field is a SCHEMA. Each key inside is an argument name. "
        "2. NEVER send the schema objects themselves as values. Send only the actual content (e.g., q='Apple'). "
        "3. Optional fields (required: false) are truly optional for you—use them only if they serve the goal. "
        "4. Strictly follow the 'instructions' provided at the action level."
    )
    openapi_url: Optional[str] = None
    actions: List[AIAction]
