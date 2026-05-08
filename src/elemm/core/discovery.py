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

import inspect
from typing import Any, List, Optional, Tuple, Union, Literal, Dict, Callable
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
        
        # Handle typing.Dict, typing.List, etc.
        if "dict" in str(annotation).lower(): raw_type = "object"
        if "list" in str(annotation).lower(): raw_type = "array"

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

class ParameterDiscovery:
    """Extrahiert Protokoll-Parameter aus Python-Funktionssignaturen."""

    def extract_parameters(self, func: Callable) -> List[Any]:
        """Konvertiert eine Funktionssignatur in eine Liste von Parameter-Objekten."""
        from .models import Parameter
        
        sig = inspect.signature(func)
        doc = inspect.getdoc(func) or ""
        # Einfache Docstring-Extraktion (nimmt die erste Zeile als Beschreibung für alle Parameter an, falls nichts spezifisches da ist)
        
        parameters = []
        sig_params = [p for n, p in sig.parameters.items() if n not in ["self", "cls", "context", "kwargs"]]
        
        # --- SMART UNBOXING ---
        # If there is only one parameter and it's a Pydantic model, extract its fields.
        if len(sig_params) == 1:
            param = sig_params[0]
            try:
                from pydantic import BaseModel
                if inspect.isclass(param.annotation) and issubclass(param.annotation, BaseModel):
                    schema = param.annotation.model_json_schema()
                    definitions = schema.get("$defs", schema.get("definitions", {}))
                    props = schema.get("properties", {})
                    required_fields = schema.get("required", [])
                    
                    for p_name, p_info in props.items():
                        # Resolve $ref if any
                        p_info = TypeMapper.resolve_refs(p_info, definitions)
                        
                        p_type = p_info.get("type", "string")
                        # Map JSON schema types to Elemm types
                        type_map = {"integer": "integer", "number": "number", "boolean": "boolean", "array": "array", "object": "object"}
                        p_type = type_map.get(p_type, "string")
                        
                        # Extract Options from Enum
                        p_options = p_info.get("enum")
                        
                        parameters.append(Parameter(
                            name=p_name,
                            type=p_type,
                            description=p_info.get("description", f"Parameter: {p_name}"),
                            required=p_name in required_fields,
                            default=p_info.get("default"),
                            options=p_options
                        ))
                    return parameters
            except:
                pass

        # Standard Discovery
        for name, param in sig.parameters.items():
            if name in ["self", "cls", "context", "kwargs"]:
                continue
            
            p_type, options = TypeMapper.map_type(param.annotation)
            
            # Default Werte
            default_val = None
            required = True
            if param.default is not inspect.Parameter.empty:
                default_val = param.default
                required = False

            parameters.append(Parameter(
                name=name,
                type=p_type,
                description=f"Parameter: {name}", 
                required=required,
                default=default_val,
                options=options
            ))
            
        return parameters
