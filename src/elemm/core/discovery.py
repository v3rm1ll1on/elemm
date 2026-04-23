from typing import List, Dict, Any, Optional, Tuple, Union, Literal
import inspect
from enum import Enum
from .models import ActionParam

def map_type(annotation: Any) -> Tuple[str, Optional[List[Any]]]:
    """
    Maps Python types/annotations to JSON Schema types and extracts enum options.
    """
    origin = getattr(annotation, "__origin__", None)
    
    # Handle Literal
    if origin is Literal:
        args = getattr(annotation, "__args__", [])
        return "string", list(args)

    if origin is Union:
        args = getattr(annotation, "__args__", [])
        annotation = next((a for a in args if a != type(None)), annotation)
        # Re-check origin after unpacking Union
        origin = getattr(annotation, "__origin__", None)
        if origin is Literal:
            args = getattr(annotation, "__args__", [])
            return "string", list(args)
    
    # Handle Enum
    if inspect.isclass(annotation) and issubclass(annotation, Enum):
        return "string", [e.value for e in annotation]

    # Handle Pydantic BaseModel (Recursive Schema)
    from pydantic import BaseModel
    if inspect.isclass(annotation) and issubclass(annotation, BaseModel):
        # We return 'object' and use the model's schema as options for processing
        try:
            schema = annotation.model_json_schema() if hasattr(annotation, "model_json_schema") else annotation.schema()
            return "object", schema
        except:
            return "object", None

    # Handle Annotated (for Field constraints)
    if hasattr(annotation, "__metadata__"):
        actual_type = annotation.__origin__
        metadata = annotation.__metadata__
        p_type, p_options = map_type(actual_type)
        # Return the type and merge metadata if possible (simplified for now)
        return p_type, p_options

    raw_type = str(getattr(annotation, "__name__", annotation)).lower()
    
    # If it's a dict from JSON schema processing
    if isinstance(annotation, dict):
        raw_type = annotation.get("type", "string")
        enum_vals = annotation.get("enum")
        if enum_vals:
            return "string", enum_vals
        
        # Check for numeric constraints
        # ... logic can be expanded here
        return raw_type, None

    mapping = {
        "str": "string", "string": "string",
        "int": "integer", "integer": "integer",
        "float": "number", "number": "number",
        "bool": "boolean", "boolean": "boolean",
        "list": "array", "array": "array",
        "dict": "object", "object": "object",
        "list[str]": "array", "list[int]": "array"
    }
    return mapping.get(raw_type, "string"), None

def resolve_refs(item: Any, definitions: Dict[str, Any], depth: int = 0) -> Any:
    """
    Recursively resolves $ref entries in a JSON schema.
    """
    if depth > 10: return item # Protection against infinite loops
    if not isinstance(item, dict): return item
    
    if "$ref" in item:
        ref_name = item["$ref"].split("/")[-1]
        if ref_name in definitions:
            # Merge ref definition into current item (excluding the $ref itself)
            base = definitions[ref_name]
            new_item = {**base, **{k: v for k, v in item.items() if k != "$ref"}}
            return resolve_refs(new_item, definitions, depth + 1)
    
    # Recurse into properties if it's an object
    if "properties" in item:
        item["properties"] = {k: resolve_refs(v, definitions, depth + 1) for k, v in item["properties"].items()}
    
    return item

def convert_actions_to_mcp_tools(actions: List[Any]) -> List[Any]:
    """
    Converts internal actions to MCP tool format.
    Centralized here to avoid circular imports and ensure consistent type mapping.
    """
    import mcp.types as types
    mcp_tools = []
    
    for a in actions:
        # Normalize to dict
        action = a if isinstance(a, dict) else {
            "id": getattr(a, "id", ""),
            "description": getattr(a, "description", ""),
            "parameters": getattr(a, "parameters", []),
            "payload": getattr(a, "payload", None)
        }
        
        action_id = action.get("id") or action.get("name")
        action_desc = action.get("description") or ""
        a_params = action.get("parameters") or []
        a_payload = action.get("payload")

        properties = {}
        required_fields = []

        # Helper to process params using map_type
        def add_param(p):
            name = p.name if hasattr(p, "name") else p.get("name")
            desc = p.description if hasattr(p, "description") else p.get("description", "")
            # Use central map_type logic
            p_type_raw = p.type if hasattr(p, "type") else p.get("type", "string")
            p_type, p_enum = map_type(p_type_raw)
            
            properties[name] = {
                "type": p_type,
                "description": desc
            }
            if p_enum:
                if p_type == "object" and isinstance(p_enum, dict):
                    # It's a Pydantic model schema
                    properties[name] = p_enum 
                else:
                    properties[name]["enum"] = p_enum
                
            if (hasattr(p, "required") and p.required) or (isinstance(p, dict) and p.get("required")):
                required_fields.append(name)

        # Parameters (Path/Query)
        if a_params:
            for p in a_params: add_param(p)

        # Payload (Body)
        if a_payload:
            if isinstance(a_payload, list):
                for p in a_payload: add_param(p)
            elif isinstance(a_payload, dict):
                for key, info in a_payload.items():
                    properties[key] = {"type": "string", "description": str(info)}
                    if "[required]" in str(info):
                        required_fields.append(key)

        clean_desc = action_desc[:160].strip() + ("..." if len(action_desc) > 160 else "")
        
        mcp_tools.append(types.Tool(
            name=action_id,
            description=clean_desc,
            inputSchema={
                "type": "object",
                "properties": properties,
                "required": list(set(required_fields))
            }
        ))
    return mcp_tools
