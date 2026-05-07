import inspect
from typing import Any, List, Optional, Tuple, Union, Literal, Dict
from enum import Enum

class TypeMapper:
    """Mapping von Python-Typen auf Protokoll-Typen."""

    @classmethod
    def map_type(cls, annotation: Any) -> Tuple[str, Optional[List[Any]]]:
        """Konvertiert eine Typ-Annotation in (Type-String, Options)."""
        origin = getattr(annotation, "__origin__", None)
        
        # Handle Literal (z.B. Literal["red", "blue"])
        if origin is Literal:
            args = getattr(annotation, "__args__", [])
            return "string", list(args)

        # Handle Union (Optional types)
        if origin is Union:
            args = getattr(annotation, "__args__", [])
            annotation = next((a for a in args if a != type(None)), annotation)
            origin = getattr(annotation, "__origin__", None)
            if origin is Literal:
                args = getattr(annotation, "__args__", [])
                return "string", list(args)
        
        # Handle Enum
        if inspect.isclass(annotation) and issubclass(annotation, Enum):
            return "string", [e.value for e in annotation]

        # Handle Pydantic BaseModel (Recursive Schema)
        try:
            from pydantic import BaseModel
            if inspect.isclass(annotation) and issubclass(annotation, BaseModel):
                schema = annotation.model_json_schema()
                return "object", schema
        except:
            pass

        raw_type = str(getattr(annotation, "__name__", annotation)).lower()
        
        mapping = {
            "str": "string", "string": "string",
            "int": "integer", "integer": "integer",
            "float": "number", "number": "number",
            "bool": "boolean", "boolean": "boolean",
            "list": "array", "array": "array",
            "dict": "object", "object": "object"
        }
        return mapping.get(raw_type, "string"), None

    @staticmethod
    def resolve_refs(item: Any, definitions: Dict[str, Any], depth: int = 0) -> Any:
        """Recursively resolves $ref entries in a JSON schema."""
        if depth > 10: return item
        if not isinstance(item, dict): return item
        
        if "$ref" in item:
            ref_name = item["$ref"].split("/")[-1]
            if ref_name in definitions:
                base = definitions[ref_name]
                new_item = {**base, **{k: v for k, v in item.items() if k != "$ref"}}
                return TypeMapper.resolve_refs(new_item, definitions, depth + 1)
        
        if "properties" in item:
            item["properties"] = {k: TypeMapper.resolve_refs(v, definitions, depth + 1) for k, v in item["properties"].items()}
        
        if "items" in item:
            if isinstance(item["items"], dict):
                item["items"] = TypeMapper.resolve_refs(item["items"], definitions, depth + 1)
        
        return item
