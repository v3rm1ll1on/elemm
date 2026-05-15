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

import logging
from typing import Dict, Any, List, Optional
from elemm.core.models import Landmark, Parameter

logger = logging.getLogger("elemm-graphql-bridge")

class GraphQLBridge:
    """
    Bridges GraphQL endpoints to Elemm Landmarks using Introspection.
    """
    
    INTROSPECTION_QUERY = """
    query IntrospectionQuery {
      __schema {
        queryType { name }
        mutationType { name }
        types {
          kind
          name
          description
          fields {
            name
            description
            args {
              name
              description
              type {
                kind
                name
                ofType { 
                  kind name 
                  ofType { 
                    kind name 
                    ofType { 
                      kind name 
                      ofType { 
                        kind name 
                        ofType { 
                          kind name 
                          ofType { kind name } 
                        }
                      }
                    }
                  } 
                }
              }
            }
            type {
              kind
              name
              ofType { 
                kind name 
                ofType { 
                  kind name 
                  ofType { 
                    kind name 
                    ofType { 
                      kind name 
                      ofType { 
                        kind name 
                        ofType { kind name } 
                      }
                    }
                  } 
                }
              }
            }
          }
        }
      }
    }
    """

    @staticmethod
    def parse_schema(schema_data: Dict[str, Any], url: str) -> Dict[str, Any]:
        """
        Parses GraphQL introspection data and returns an Elemm-compatible structure.
        """
        schema = schema_data.get("__schema") or {}
        
        qt_obj = schema.get("queryType") or {}
        query_type_name = qt_obj.get("name", "Query")
        
        mt_obj = schema.get("mutationType") or {}
        mutation_type_name = mt_obj.get("name", "Mutation")
        
        types = {t["name"]: t for t in schema.get("types", []) if t.get("name")}
        landmarks = []
        
        # Process Queries
        query_type = types.get(query_type_name)
        if query_type:
            landmarks.extend(GraphQLBridge._process_fields(query_type, "Query", url))
            
        # Process Mutations
        mutation_type = types.get(mutation_type_name)
        if mutation_type:
            landmarks.extend(GraphQLBridge._process_fields(mutation_type, "Mutation", url))
            
        # Convert to dicts for backward compatibility with tests and services
        dict_landmarks = []
        for lm in landmarks:
            d = lm.model_dump(exclude_none=True)
            # Legacy fields
            d["name"] = lm.id
            
            # Inject legacy inputSchema
            props = {}
            required = []
            for p in lm.parameters or []:
                # Try to find gql_type in parameter or its meta
                p_dict = p.model_dump(exclude_none=True)
                props[p.name] = {
                    "type": p.type,
                    "description": p.description,
                    "gql_type": p_dict.get("meta", {}).get("gql_type") or p_dict.get("gql_type")
                }
                if p.required:
                    required.append(p.name)
            d["inputSchema"] = {"type": "object", "properties": props, "required": required}
            dict_landmarks.append(d)
            
        return {
            "landmarks": dict_landmarks,
            "tools": dict_landmarks, # Compatibility alias
            "base_url": url,
            "title": GraphQLBridge.urlparse_title(url)
        }

    @staticmethod
    def _process_fields(type_obj: Dict[str, Any], category: str, url: str) -> List[Landmark]:
        landmarks = []
        for field in type_obj.get("fields", []):
            name = field["name"]
            description = field.get("description", f"{category} operation: {name}")
            
            # Map Arguments to Parameter Models
            params_list = []
            for arg in field.get("args", []):
                arg_name = arg["name"]
                arg_type_info = GraphQLBridge._get_type_info(arg["type"])
                
                params_list.append(Parameter(
                    name=arg_name,
                    type=arg_type_info["json_type"],
                    description=arg.get("description", ""),
                    required=arg_type_info["is_required"],
                    meta={"gql_type": arg_type_info.get("gql_type")}
                ))

            # Create Official Landmark
            landmarks.append(Landmark(
                id=f"{category}:{name}",
                description=description,
                parameters=params_list,
                type="action",
                meta={
                    "type": "graphql",
                    "operation_type": category.lower(),
                    "field_name": name,
                    "base_url": url
                }
            ))
        return landmarks

    @staticmethod
    def _get_type_info(type_obj: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Recursive helper to extract type information."""
        if not type_obj:
            return {"json_type": "string", "is_required": False, "gql_type": ""}
            
        kind = type_obj.get("kind")
        name = type_obj.get("name")
        
        if kind == "NON_NULL":
            inner = GraphQLBridge._get_type_info(type_obj.get("ofType"))
            if inner.get("gql_type") is not None:
                inner["gql_type"] = f"{inner['gql_type']}!"
            inner["is_required"] = True
            return inner
            
        if kind == "LIST":
            inner = GraphQLBridge._get_type_info(type_obj.get("ofType"))
            # is_required aus dem inneren Typ propagieren, damit der äußere NON_NULL-Wrapper
            # (falls vorhanden) korrekt das '!' anhängen kann — z.B. [ID!]! statt [ID!]
            g_inner = inner.get("gql_type") or "String"
            return {
                "json_type": "array",
                "is_required": inner.get("is_required", False),
                "gql_type": f"[{g_inner}]"
            }
            
        # Basic Scalar Mapping
        mapping = {
            "String": "string",
            "Int": "integer",
            "Float": "number",
            "Boolean": "boolean",
            "ID": "string"
        }
        
        return {
            "json_type": mapping.get(name, "object" if kind == "INPUT_OBJECT" else "string"),
            "gql_type": name,
            "is_required": False
        }

    @staticmethod
    def urlparse_title(url: str) -> str:
        from urllib.parse import urlparse
        return urlparse(url).netloc
