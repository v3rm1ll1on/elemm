# Copyright (C) 2026 Marc Stöcker
# Website: https://elemm.dev
#
# This program is licensed under the Business Source License 1.1 (BSL 1.1).
# See the LICENSE file in the root directory for details.

from typing import Any, Dict, List, Optional, Union
from .models import Parameter

class SchemaResolver:
    """
    Zentraler Resolver für JSON-Schemas und $ref-Verweise im Elemm-Protokoll.
    """

    @staticmethod
    def resolve(schema: Any, spec: Dict[str, Any], depth: int = 0) -> Any:
        """
        Löst rekursiv alle $ref-Verweise in einem Schema auf Basis einer Spezifikation auf.
        Unterstützt OpenAPI 3.0 (components/schemas) und Swagger 2.0 (definitions).
        """
        if depth > 10: return schema # Safety break
        
        if isinstance(schema, list):
            return [SchemaResolver.resolve(item, spec, depth + 1) for item in schema]
            
        if not isinstance(schema, dict):
            return schema
            
        if "$ref" in schema:
            ref_path = schema["$ref"].split("/")
            
            # OpenAPI 3.0 / Components
            if len(ref_path) >= 4 and ref_path[0] == "#" and ref_path[1] == "components":
                root_key = ref_path[2] # schemas, parameters, etc.
                schema_name = ref_path[3]
                resolved = spec.get("components", {}).get(root_key, {}).get(schema_name, {})
                return SchemaResolver.resolve(resolved, spec, depth + 1)
                
            # Swagger 2.0 / Definitions
            elif len(ref_path) >= 3 and ref_path[0] == "#" and ref_path[1] == "definitions":
                schema_name = ref_path[2]
                resolved = spec.get("definitions", {}).get(schema_name, {})
                return SchemaResolver.resolve(resolved, spec, depth + 1)
                
            # Generic Fallback (last part of path)
            else:
                schema_name = ref_path[-1]
                # Try to find it anywhere in components or definitions
                for root in ["components", "definitions"]:
                    for group in spec.get(root, {}).values() if root == "components" else [spec.get("definitions", {})]:
                        if isinstance(group, dict) and schema_name in group:
                            return SchemaResolver.resolve(group[schema_name], spec, depth + 1)

        # Rekursion in Properties und Items
        resolved_schema = schema.copy()
        if "properties" in resolved_schema:
            resolved_schema["properties"] = {
                k: SchemaResolver.resolve(v, spec, depth + 1) 
                for k, v in resolved_schema["properties"].items()
            }
        if "items" in resolved_schema:
            resolved_schema["items"] = SchemaResolver.resolve(resolved_schema["items"], spec, depth + 1)
            
        return resolved_schema

from .models import Landmark, Parameter

class SignatureGenerator:
    """
    Erzeugt technische Signaturen (z.B. TypeScript) aus Elemm-Tool-Metadaten.
    """

    @staticmethod
    def to_typescript_signature(tool: Union[Landmark, Dict[str, Any]]) -> str:
        """
        Erzeugt eine TypeScript-Funktionssignatur für ein Tool.
        """
        if isinstance(tool, Landmark):
            name = tool.id
            description = tool.description
            params_list = tool.parameters or []
            returns = tool.returns or "any"
            # Handle Response Schema if available
            schema = getattr(tool, 'response_schema', None)
        else:
            name = tool.get("name") or tool.get("id") or "unknown_action"
            description = tool.get("description", "No description")
            input_schema = tool.get("inputSchema", {})
            required = input_schema.get("required", [])
            props = input_schema.get("properties", {})
            params_list = []
            
            if "parameters" in tool and isinstance(tool["parameters"], list):
                for p in tool["parameters"]:
                    params_list.append(Parameter(
                        name=p.get("name", ""),
                        type=p.get("type", "string"),
                        description=p.get("description", ""),
                        required=p.get("required", False)
                    ))
            else:
                for p_name, p_info in props.items():
                    params_list.append(Parameter(
                        name=p_name,
                        type=p_info.get("type", "string"),
                        description=p_info.get("description", ""),
                        required=p_name in required
                    ))
            returns = tool.get("returns", "any")
            schema = tool.get("outputSchema")
        
        params = []
        for p in params_list:
            opt = "" if p.required else "?"
            params.append(f"{p.name}{opt}: {p.type}")
            
        # Outputs
        ret_type = SignatureGenerator._schema_to_ts_type(schema) if schema else returns
        
        # Outputs
        ret_type = SignatureGenerator._schema_to_ts_type(schema) if schema else returns
        
        # JSDoc description with Redundancy Filter
        jsdoc = ""
        if description and len(description) > 3:
            norm_id = name.lower().replace("_", " ").replace(":", " ").strip()
            norm_desc = description.lower().strip()
            if norm_id != norm_desc and norm_id.replace(" ", "") != norm_desc.replace(" ", ""):
                jsdoc = f"/** Description: {description} */\n"
                
        return f"{jsdoc}function call_action(action: '{name}', parameters: {{ {', '.join(params)} }}): {ret_type};"

    @staticmethod
    def _schema_to_ts_type(schema: Any, depth: int = 0) -> str:
        """Konvertiert ein JSON-Schema in einen aggressiv 'gesquashten' TS-Typ-String."""
        if depth > 2 or not isinstance(schema, dict): return "any"
        
        s_type = schema.get("type", "any")
        
        if s_type == "object" and "properties" in schema:
            props_dict = schema["properties"]
            keys = list(props_dict.keys())
            # Zeige maximal 5 Felder, um Bloat zu vermeiden
            visible_keys = keys[:5]
            props = [f"{k}: {SignatureGenerator._schema_to_ts_type(props_dict[k], depth + 1)}" for k in visible_keys]
            
            if len(keys) > 5:
                props.append(f"... +{len(keys) - 5} more fields")
                
            return f"{{ {', '.join(props)} }}"
        
        if s_type == "array" and "items" in schema:
            # Kompakte Array-Darstellung
            return f"Array<{SignatureGenerator._schema_to_ts_type(schema['items'], depth + 1)}>"
            
        return s_type