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

    raw_type = str(getattr(annotation, "__name__", annotation)).lower()
    
    # If it's a dict from JSON schema processing
    if isinstance(annotation, dict):
        raw_type = annotation.get("type", "string")
        enum_vals = annotation.get("enum")
        if enum_vals:
            return "string", enum_vals

    mapping = {
        "str": "string", "string": "string",
        "int": "integer", "integer": "integer",
        "float": "number", "number": "number",
        "bool": "boolean", "boolean": "boolean",
        "list": "array", "array": "array",
        "dict": "object", "object": "object"
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
