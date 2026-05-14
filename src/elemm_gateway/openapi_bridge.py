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

import json
import logging
import re
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional

logger = logging.getLogger("elemm-openapi-bridge")

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
        tools = []
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
                
                # 3. Parameters (Simplified extraction for Elemm)
                # We want to create a JSON schema for the input
                properties = {}
                required = []
                
                # Merge path-level and operation-level parameters
                parameters = path_params + details.get("parameters", [])
                resolved_params = []
                for param in parameters:
                    # Resolve internal $ref if present
                    if "$ref" in param:
                        ref_path = param["$ref"].split("/")
                        if ref_path[0] == "#" and ref_path[1] == "components" and ref_path[2] == "parameters":
                            param_name = ref_path[3]
                            param = spec.get("components", {}).get("parameters", {}).get(param_name, {})
                        else:
                            continue # Skip unsupported refs for now
                            
                    p_name = param.get("name")
                    if not p_name:
                        continue
                    
                    resolved_params.append(param)
                        
                    p_schema = param.get("schema", {"type": "string"})
                    p_desc = param.get("description", "")
                    
                    properties[p_name] = {
                        "type": p_schema.get("type", "string"),
                        "description": p_desc,
                        "location": param.get("in", "query")
                    }
                    if param.get("required"):
                        required.append(p_name)
                
                # Handle requestBody
                body = details.get("requestBody", {})
                content = body.get("content", {})
                json_content = content.get("application/json", {})
                body_schema = json_content.get("schema", {})
                
                if body_schema:
                    # In a real implementation, we'd merge or nest this.
                    # For simplicity in this PoC, we add a 'body' field if it's complex,
                    # or flatten it if it's a simple object.
                    if body_schema.get("type") == "object" and "properties" in body_schema:
                        for b_name, b_prop in body_schema["properties"].items():
                            properties[b_name] = b_prop
                            if b_name in body_schema.get("required", []):
                                required.append(b_name)
                    else:
                        properties["payload"] = body_schema
                        if body.get("required"):
                            required.append("payload")

                # Inject Universal Parameters into Schema
                properties["_select"] = {
                    "type": "string",
                    "description": "Fields to return (comma-separated). Use dot-notation for nested objects (e.g. 'author.name')."
                }
                properties["_filter"] = {
                    "type": "string",
                    "description": "Basic equality filter (e.g. status=active)"
                }
                properties["_limit"] = {
                    "type": "integer",
                    "description": "Max number of items to return"
                }

                tools.append({
                    "name": landmark_id,
                    "description": description,
                    "inputSchema": {
                        "type": "object",
                        "properties": properties,
                        "required": required
                    },
                    "meta": {
                        "path": path,
                        "method": method.upper(),
                        "base_url": base_url,
                        "params": [
                            {"name": p["name"], "in": p.get("in", "query")} 
                            for p in resolved_params if "name" in p
                        ]
                    }
                })
        
        # Extract Security Schemes
        security_schemes = spec.get("components", {}).get("securitySchemes", {})
        if not security_schemes and "securityDefinitions" in spec: # Swagger 2.0
            security_schemes = spec.get("securityDefinitions", {})
            
        global_security = spec.get("security", [])

        return {
            "tools": tools,
            "tag_metadata": tag_metadata,
            "info": spec.get("info", {}),
            "base_url": base_url,
            "security_schemes": security_schemes,
            "global_security": global_security
        }

    @staticmethod
    def generate_virtual_manifest(parsed_data: Dict[str, Any]) -> str:
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
            for t in tag_tools[:20]:
                req_params = t.get("inputSchema", {}).get("required", [])
                display_params = [p for p in req_params if not p.startswith("_")]
                hint = f" (Required: {', '.join(display_params)})" if display_params else ""
                lines.append(f"  - Tool: `{t['name']}`{hint}")
                
            if len(tag_tools) > 20:
                lines.append(f"  - ... and {len(tag_tools) - 20} more. (Use `inspect_landmark('{tag}')` for full list)")

        return "\n".join(lines)

    @staticmethod
    def get_tool_signature(parsed_data: Dict[str, Any], landmark_id: str) -> str:
        """Helper for deep inspection without bloating the main manifest."""
        tools = parsed_data.get("tools", [])
        selected = [t for t in tools if t["name"] == landmark_id or t["name"].startswith(landmark_id + "_")]
        if not selected: return ""
        
        lines = ["### TECHNICAL SIGNATURES", "```typescript"]
        for t in selected:
            schema = t.get("inputSchema", {})
            params = [f"{n}{'' if n in schema.get('required', []) else '?'}: {d.get('type', 'any')}" for n, d in schema.get("properties", {}).items()]
            lines.append(f"/** {t.get('description', 'No desc')} */\nfunction call_action(action: '{t['name']}', parameters: {{ {', '.join(params)} }}): any;\n")
        lines.append("```")
        return "\n".join(lines)
