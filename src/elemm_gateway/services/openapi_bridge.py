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
import re
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional
from elemm.core.models import Landmark, Parameter
from elemm.core.schema import SchemaResolver, SignatureGenerator

class OpenAPIBridge:
    """
    Bridges OpenAPI specifications to Elemm Landmarks.
    """
    
    @staticmethod
    def parse_spec(spec: Dict[str, Any], fallback_base_url: str) -> Dict[str, Any]:
        """
        Parses an OpenAPI spec and returns a structure compatible with Elemm's internal tool registry.
        """
        base_url = None
        landmarks = []
        paths = spec.get("paths", {})
        
        # Determine the actual base URL from the spec if available
        servers = spec.get("servers", [])
        if servers:
            base_url = servers[0].get("url", "")
            # Handle relative URLs in servers
            if base_url.startswith("/"):
                # Construct from fallback_base_url (which is the directory of the spec)
                parsed_fallback = urlparse(fallback_base_url)
                base_url = f"{parsed_fallback.scheme}://{parsed_fallback.netloc}{base_url}"
        elif "host" in spec:
            host = spec["host"]
            base_path = spec.get("basePath", "")
            scheme = spec.get("schemes", ["https"])[0]
            base_url = f"{scheme}://{host}{base_path}"
        
        if not base_url:
            base_url = fallback_base_url
        
        # Strip trailing slash from base_url
        base_url = base_url.rstrip("/")

        # Extract Tag Metadata (Landmark descriptions)
        tag_metadata = {}
        for tag_obj in spec.get("tags", []):
            tag_name = tag_obj.get("name")
            if tag_name:
                tag_metadata[tag_name] = tag_obj.get("description", f"Operations related to {tag_name}")

        for path, methods in paths.items():
            if not isinstance(methods, dict):
                continue
                
            # Extract path-level parameters
            path_params = methods.get("parameters", [])
            
            for method, details in methods.items():
                if method == "parameters" or not isinstance(details, dict):
                    continue
                # 1. Landmark ID: Use colon for Elemm hierarchy
                tag = details.get("tags", ["General"])[0]
                op_id = details.get("operationId", f"{method}_{path.strip('/')}")
                
                # Sanitize: use colon for hierarchy as per official Elemm protocol
                raw_id = f"{tag}:{op_id}"
                landmark_id = re.sub(r'[^a-zA-Z0-9_:-]', '_', raw_id).strip('_').replace('__', '_')
                
                # 2. Description
                description = details.get("summary", details.get("description", "No description provided."))
                
                # 3. Parameters (Official Landmark Models)
                params_list = []
                
                # Merge path-level and operation-level parameters
                parameters = path_params + details.get("parameters", [])
                for param in parameters:
                    # Fully resolve all $refs recursively
                    param = SchemaResolver.resolve(param, spec)
                    p_name = param.get("name")
                    if not p_name: continue
                    
                    p_schema = param.get("schema", {"type": "string"})
                    params_list.append(Parameter(
                        name=p_name,
                        type=p_schema.get("type", "string"),
                        description=param.get("description", ""),
                        required=bool(param.get("required", False)),
                        location=param.get("in", "query")
                    ))
                
                # Handle requestBody
                body = details.get("requestBody", {})
                content = body.get("content", {})
                json_content = content.get("application/json", {})
                body_schema = json_content.get("schema", {})
                
                if body_schema:
                    body_schema = SchemaResolver.resolve(body_schema, spec)
                    if body_schema.get("type") == "object" and "properties" in body_schema:
                        for b_name, b_prop in body_schema["properties"].items():
                            params_list.append(Parameter(
                                name=b_name,
                                type=b_prop.get("type", "string"),
                                description=b_prop.get("description", ""),
                                required=b_name in body_schema.get("required", []),
                                location="body"
                            ))
                    else:
                        params_list.append(Parameter(
                            name="payload",
                            type=body_schema.get("type", "object"),
                            description="Full request body payload",
                            required=bool(body.get("required", False)),
                            location="body"
                        ))

                # 4. Responses (Output Schema)
                responses = details.get("responses", {})
                ok_response = responses.get("200", responses.get(200, {}))
                content = ok_response.get("content", {})
                json_res = content.get("application/json", {})
                output_schema = json_res.get("schema", {})
                if output_schema:
                    output_schema = SchemaResolver.resolve(output_schema, spec)

                # Create Official Landmark
                ret_type = "any"
                if isinstance(output_schema, dict) and output_schema:
                    ret_type = SignatureGenerator._schema_to_ts_type(output_schema)
                landmarks.append(Landmark(
                    id=landmark_id,
                    description=description,
                    parameters=params_list,
                    returns=ret_type,
                    response_schema=output_schema,
                    type="action",
                    meta={
                        "path": path,
                        "method": method.upper(),
                        "base_url": base_url,
                        "tag": tag
                    }
                ))

        # Extract Security Schemes
        security_schemes = spec.get("components", {}).get("securitySchemes", {})
        if not security_schemes and "securityDefinitions" in spec: # Swagger 2.0
            security_schemes = spec.get("securityDefinitions", {})
            
        global_security = spec.get("security", [])

        # Convert to dicts for backward compatibility with tests and gateway logic
        dict_landmarks = []
        for lm in landmarks:
            d = lm.model_dump(exclude_none=True)
            # Legacy fields
            d["name"] = lm.id
            
            # Inject legacy inputSchema
            props = {}
            required = []
            for p in lm.parameters or []:
                props[p.name] = {
                    "type": p.type,
                    "description": p.description
                }
                if p.required:
                    required.append(p.name)
            d["inputSchema"] = {"type": "object", "properties": props, "required": required}
            dict_landmarks.append(d)

        return {
            "landmarks": dict_landmarks,
            "tools": dict_landmarks, # Compatibility alias
            "tag_metadata": tag_metadata,
            "info": spec.get("info", {}),
            "base_url": base_url,
            "security_schemes": security_schemes,
            "global_security": global_security
        }

    @staticmethod
    def _resolve_refs(schema: Any, spec: Dict[str, Any], depth: int = 0) -> Any:
        """Recursively resolves $ref pointers in a JSON schema."""
        if depth > 10: return schema # Safety break
        
        if isinstance(schema, list):
            return [OpenAPIBridge._resolve_refs(item, spec, depth + 1) for item in schema]
            
        if not isinstance(schema, dict):
            return schema
            
        if "$ref" in schema:
            ref_path = schema["$ref"].split("/")
            if ref_path[0] == "#" and ref_path[1] == "components" and ref_path[2] == "schemas":
                schema_name = ref_path[3]
                resolved = spec.get("components", {}).get("schemas", {}).get(schema_name, {})
                # Continue resolving inside the resolved schema
                return OpenAPIBridge._resolve_refs(resolved, spec, depth + 1)
            # Support Swagger 2.0 style refs
            elif ref_path[0] == "#" and ref_path[1] == "definitions":
                schema_name = ref_path[2]
                resolved = spec.get("definitions", {}).get(schema_name, {})
                return OpenAPIBridge._resolve_refs(resolved, spec, depth + 1)
        
        # Recurse into properties and items
        resolved_schema = schema.copy()
        if "properties" in resolved_schema:
            resolved_schema["properties"] = {
                k: OpenAPIBridge._resolve_refs(v, spec, depth + 1) 
                for k, v in resolved_schema["properties"].items()
            }
        if "items" in resolved_schema:
            resolved_schema["items"] = OpenAPIBridge._resolve_refs(resolved_schema["items"], spec, depth + 1)
            
        return resolved_schema

    @staticmethod
    def generate_virtual_manifest(parsed_data: Dict[str, Any], limit: int = 20) -> str:
        """
        Generates a High-Fidelity Elemm v2 manifest (Gold Standard).
        """
        info = parsed_data.get("info", {})
        title = info.get("title", "Dynamic API")
        version = info.get("version", "1.0.0")
        tag_metadata = parsed_data.get("tag_metadata", {})
        
        tools = parsed_data.get("tools", [])
        
        # Group tools by tags (Landmarks)
        landmarks = {}
        for t in tools:
            tag = t["name"].split("_", 1)[0] if "_" in t["name"] else "General"
            if tag not in landmarks:
                landmarks[tag] = []
            landmarks[tag].append(t)

        from elemm_gateway.components import ManifestBuilder
        
        lines = [
            ManifestBuilder.build_header(title, version),
            "### LANDMARK TOPOLOGY",
            "> [!IMPORTANT]",
            "> Use 'inspect_landmark(landmark_id=\"...\")' to get the required TypeScript signatures BEFORE execution.",
            ""
        ]

        for tag, tag_tools in landmarks.items():
            desc = tag_metadata.get(tag, f"Operations related to {tag}")
            # Use 'Landmark:' prefix for tags to ensure they are seen as areas
            lines.append(f"- Landmark: `{tag}` (Area/Namespace) - {desc}")
            
            # Use standard Elemm tool list format so the parser can find them
            visible_tools = tag_tools[:limit]
            remaining = len(tag_tools) - limit

            for t in visible_tools:
                req_params = t.get("inputSchema", {}).get("required", [])
                display_params = [p for p in req_params if not p.startswith("_")]
                hint = f" (Required: {', '.join(display_params)})" if display_params else ""
                ret_hint = f" -> {t.get('returns', 'any')}"
                lines.append(f"  - Tool: `{t['name']}`{hint}{ret_hint}")
                
            if remaining > 0:
                lines.append(f"  - (... and {remaining} more tools. Use `inspect_landmark(landmark_id=\"{tag}\")` for full list)")

        return "\n".join(lines)

    @staticmethod
    def get_tool_signature(parsed_data: Dict[str, Any], landmark_id: str) -> str:
        """Helper for deep inspection using core SignatureGenerator."""
        tools = parsed_data.get("tools", [])
        selected = [t for t in tools if t["name"] == landmark_id or t["name"].lower() == landmark_id.lower()]
        if not selected: return ""
        
        lines = ["### TECHNICAL SIGNATURES", "```typescript"]
        for t in selected:
            lines.append(SignatureGenerator.to_typescript_signature(t))
        lines.append("```")
        return "\n".join(lines)
