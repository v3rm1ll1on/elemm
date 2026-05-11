import json
import logging
import re
from typing import Dict, Any, List, Optional

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
                ofType { kind name ofType { kind name } }
              }
            }
            type {
              kind
              name
              ofType { kind name ofType { kind name } }
            }
          }
        }
      }
    }
    """

    @staticmethod
    def parse_schema(schema_data: Dict[str, Any], url: str) -> Dict[str, Any]:
        """
        Parses GraphQL introspection data and returns an Elemm-compatible tool structure.
        """
        schema = schema_data.get("__schema") or {}
        
        qt_obj = schema.get("queryType") or {}
        query_type_name = qt_obj.get("name", "Query")
        
        mt_obj = schema.get("mutationType") or {}
        mutation_type_name = mt_obj.get("name", "Mutation")
        
        types = {t["name"]: t for t in schema.get("types", []) if t.get("name")}
        tools = []
        
        # Process Queries
        query_type = types.get(query_type_name)
        if query_type:
            tools.extend(GraphQLBridge._process_fields(query_type, "Query", url))
            
        # Process Mutations
        mutation_type = types.get(mutation_type_name)
        if mutation_type:
            tools.extend(GraphQLBridge._process_fields(mutation_type, "Mutation", url))
            
        return {
            "tools": tools,
            "base_url": url,
            "title": urlparse_title(url)
        }

    @staticmethod
    def _process_fields(type_obj: Dict[str, Any], category: str, url: str) -> List[Dict[str, Any]]:
        tools = []
        for field in type_obj.get("fields", []):
            name = field["name"]
            description = field.get("description", f"{category} operation: {name}")
            
            # Map Arguments to JSON Schema
            properties = {}
            required = []
            
            for arg in field.get("args", []):
                arg_name = arg["name"]
                arg_type_info = GraphQLBridge._get_type_info(arg["type"])
                
                properties[arg_name] = {
                    "type": arg_type_info["json_type"],
                    "description": arg.get("description", ""),
                    "gql_type": arg_type_info.get("gql_type")
                }
                if arg_type_info["is_required"]:
                    required.append(arg_name)

            # Universal Elemm Parameters
            properties["_select"] = {"type": "string", "description": "[universal] Fields to return (comma-separated). Use dot-notation for nested objects (e.g. 'origin.name')."}
            
            tools.append({
                "name": f"{category}_{name}",
                "description": description,
                "inputSchema": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                },
                "meta": {
                    "type": "graphql",
                    "operation_type": category.lower(),
                    "field_name": name,
                    "base_url": url,
                    "inputSchema": {
                        "type": "object",
                        "properties": properties,
                        "required": required
                    }
                }
            })
        return tools

    @staticmethod
    def _get_type_info(type_obj: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Recursive helper to extract type information."""
        if not type_obj:
            return {"json_type": "string", "is_required": False}
            
        kind = type_obj.get("kind")
        name = type_obj.get("name")
        
        if kind == "NON_NULL":
            inner = GraphQLBridge._get_type_info(type_obj.get("ofType"))
            if inner.get("gql_type"):
                inner["gql_type"] = f"{inner['gql_type']}!"
            inner["is_required"] = True
            return inner
            
        if kind == "LIST":
            inner = GraphQLBridge._get_type_info(type_obj.get("ofType"))
            return {
                "json_type": "array", 
                "is_required": False, 
                "gql_type": f"[{inner.get('gql_type', 'String')}]"
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

def urlparse_title(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(url).netloc
