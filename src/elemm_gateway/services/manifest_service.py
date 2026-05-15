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

import httpx
import json
import yaml
import logging
import re
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional, Union

from .openapi_bridge import OpenAPIBridge
from .graphql_bridge import GraphQLBridge
from .manifest import ManifestBuilder

logger = logging.getLogger("elemm-gateway")

class ManifestService:
    """
    Service for probing, parsing, and inspecting Elemm-compliant manifests 
    across Native, OpenAPI, and GraphQL interfaces.
    """
    
    @staticmethod
    def inject_globals(manifest: str, full: bool = False, inject_metadata: bool = True) -> str:
        """Injects gateway globals and appropriate protocol rules."""
        return ManifestBuilder.inject_globals(manifest, full, inject_metadata)

    @staticmethod
    def get_landmarks_summary(site_data: Dict[str, Any], security_policy=None, limit: int = 20) -> str:
        """Fallback implementation to generate a simple get_landmarks response."""
        tools = site_data.get("tools", [])
        lines = ["### AVAILABLE LANDMARKS\n"]
        visible = 0
        
        # We need to extract unique landmarks (the prefixes)
        landmarks = {}
        tool_counts = {}
        for t in tools:
            name = t.get("name", "")
            # check security
            if security_policy and not security_policy.is_action_allowed(name)["allowed"]:
                continue
            
            # Group by tag/prefix
            prefix = name.split(":")[0] if ":" in name else (name.split("_")[0] if "_" in name else name)
            if prefix not in landmarks:
                landmarks[prefix] = t.get("description", f"No description provided.")
                tool_counts[prefix] = 0
            tool_counts[prefix] += 1
                
        for prefix, desc in list(landmarks.items())[:limit]:
            lines.append(f"- **{prefix}**: ({tool_counts[prefix]} tools) {desc}")
            visible += 1
            
        remaining = len(landmarks) - visible
        if remaining > 0:
            lines.append(f"\n- (... and {remaining} more landmarks available. Use `get_manifest(landmark_id=\"...\")` with a specific ID to explore other areas.)")
            
        return "\n".join(lines)

    @staticmethod
    def normalize_bridge_to_elemm(bridge_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep-normalizes Bridge data (OpenAPI/GraphQL) into the official Elemm Manifest JSON format.
        This ensures the UI and Agents see no difference between Native and Bridged sources.
        """
        landmarks = []
        for tool in bridge_data.get("tools", []):
            # Extract parameters from inputSchema
            params = []
            schema = tool.get("inputSchema", {})
            for name, p in schema.get("properties", {}).items():
                # Skip internal hygiene params if they are already in the tool meta
                if name in ["_select", "_filter", "_limit", "_offset"]:
                    continue
                params.append({
                    "name": name,
                    "type": p.get("type", "string"),
                    "description": p.get("description", ""),
                    "required": name in schema.get("required", [])
                })
            
            landmarks.append({
                "id": tool["name"],
                "type": "tool",
                "description": tool.get("description", ""),
                "parameters": params,
                "is_tool": True,
                "meta": tool.get("meta", {})
            })
            
        return {
            "version": "1.2.0-virtual",
            "title": bridge_data.get("title", "Bridged API"),
            "base_url": bridge_data.get("base_url", ""),
            "landmarks": landmarks
        }

    @staticmethod
    async def inspect_url(url: str, landmark_id: Optional[str] = None, vault_manager=None, limit: int = 100, output_format: str = "markdown") -> Dict[str, Any]:
        """Probes a URL for various Elemm interfaces and returns data in requested format."""
        
        async with httpx.AsyncClient() as client:
            headers = {}
            if vault_manager:
                headers = vault_manager.get_headers(url)

            # 1. PRIORITY: Check for Native Elemm (The high-perf choice)
            try:
                inspect_url = f"{url.rstrip('/')}/.well-known/elemm-manifest.md"
                params = {"technical": "true", "limit": limit}
                if landmark_id: params["landmark_id"] = landmark_id
                if output_format == "json": params["format"] = "json"
                
                resp = await client.get(inspect_url, params=params, headers=headers, follow_redirects=True, timeout=5.0)
                if resp.status_code == 200:
                    text = resp.text
                    if not ("<html>" in text.lower() or "<!doctype html>" in text.lower()):
                        if output_format == "json":
                            try: return {"status": "success", "type": "native", "data": resp.json()}
                            except: pass
                        return {"status": "success", "type": "native", "manifest": text}
            except: pass

            # 2. Check for GraphQL
            try:
                gql_url = url if url.rstrip('/').endswith('/graphql') else f"{url.rstrip('/')}/graphql"
                probe_resp = await client.post(gql_url, json={"query": GraphQLBridge.INTROSPECTION_QUERY}, timeout=8.0)
                if probe_resp.status_code == 200 and "data" in probe_resp.json():
                    schema_data = probe_resp.json().get("data")
                    parsed = GraphQLBridge.parse_schema(schema_data, gql_url)
                    manifest_md = GraphQLBridge.generate_virtual_manifest(parsed)
                    normalized = ManifestService.normalize_bridge_to_elemm(parsed)
                    
                    return {
                        "status": "success", "type": "graphql", "url": gql_url, 
                        "manifest": manifest_md, "data": normalized, "tools": parsed.get("tools", [])
                    }
            except: pass

            # 3. Check for OpenAPI
            try:
                spec_urls = []
                if any(url.lower().endswith(ext) for ext in [".json", ".yaml", ".yml"]):
                    spec_urls.append(url)
                spec_urls += [f"{url.rstrip('/')}{p}" for p in ["/openapi.json", "/swagger.json", "/api-docs"]]
                
                for spec_url in spec_urls:
                    resp = await client.get(spec_url, timeout=5.0)
                    if resp.status_code == 200:
                        text = resp.text
                        if "<html>" in text.lower() or "<!doctype html>" in text.lower():
                            continue
                        try: spec = resp.json()
                        except: 
                            try: spec = yaml.safe_load(text)
                            except: continue
                        
                        if isinstance(spec, dict) and (spec.get("openapi") or spec.get("swagger")):
                            parsed = OpenAPIBridge.parse_spec(spec, url)
                            manifest_md = OpenAPIBridge.generate_virtual_manifest(parsed)
                            normalized = ManifestService.normalize_bridge_to_elemm(parsed)
                            
                            return {
                                "status": "success", "type": "openapi", "url": spec_url, 
                                "manifest": manifest_md, "data": normalized, "tools": parsed.get("tools", [])
                            }
            except Exception as e:
                logger.debug(f"OpenAPI probe failed for {url}: {e}")

            return {"status": "error", "message": f"Could not find a supported interface at {url}"}

            return {"status": "error", "message": f"Could not find a supported interface at {url}"}

    @classmethod
    async def search_landmarks(cls, url: str, site_data: dict, query: str, limit: int = 100, offset: int = 0, output_format: str = "markdown") -> Union[str, Dict[str, Any]]:
        """Durchsucht Landmarks auf dem nativen Server oder in Brücken-Daten."""
        site_type = site_data.get("type", "native")
        
        # 1. Native Search (Remote)
        if site_type == "native":
            async with httpx.AsyncClient() as client:
                params = {
                    "query": query, "limit": limit, "offset": offset,
                    "format": "json" if output_format == "json" else "markdown"
                }
                try:
                    resp = await client.get(f"{url.rstrip('/')}/.well-known/elemm/search", params=params, timeout=10.0)
                    if resp.status_code == 200:
                        return resp.json() if output_format == "json" else resp.text
                    return {"status": "error", "message": f"Remote search failed: {resp.status_code}"}
                except Exception as e:
                    return {"status": "error", "message": f"Search error: {str(e)}"}

        # 2. Bridge Search (Local in site_data)
        import re
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        tools = site_data.get("tools", [])
        matches = []
        for t in tools:
            name = t.get("name", t.get("id", ""))
            desc = t.get("description", "")
            if pattern.search(name) or pattern.search(desc):
                matches.append(t)
        
        # Pagination
        total = len(matches)
        paginated = matches[offset : offset + limit]
        
        if output_format == "json":
            return {
                "status": "success", "type": site_type, 
                "landmarks": paginated,
                "pagination": {"total": total, "offset": offset, "limit": limit, "has_more": (offset + limit) < total}
            }
        
        # Markdown Fallback for Bridges
        lines = [f"### SEARCH RESULTS FOR: {query}\n"]
        for m in paginated:
            lines.append(f"- **{m.get('name', m.get('id'))}**: {m.get('description', '')}")
        return "\n".join(lines)

    @staticmethod
    async def inspect_landmark(site_url: str, landmark_id: str, vault_manager=None, limit: int = 100, offset: int = 0, output_format: str = "markdown", site_type: str = "native") -> Dict[str, Any]:
        """Generates technical signatures for specific landmarks."""
        
        def map_bridge_tool(tool):
            """Helper to map Bridge inputSchema to Elemm parameters."""
            if not tool: return None
            params = []
            schema = tool.get("inputSchema", {})
            for name, p in schema.get("properties", {}).items():
                params.append({
                    "name": name,
                    "type": p.get("type", "string"),
                    "description": p.get("description", "")
                })
            return {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": params,
                "is_tool": True
            }

        async with httpx.AsyncClient() as client:
            try:
                # 1. Native Elemm Route
                if site_type == "native":
                    inspect_url = f"{site_url.rstrip('/')}/.well-known/elemm-manifest.md"
                    params = {"landmark_id": landmark_id, "technical": "true", "limit": 100, "offset": offset}
                    if output_format == "json": params["format"] = "json"
                    
                    resp = await client.get(inspect_url, params=params, follow_redirects=True)
                    if resp.status_code == 200:
                        if output_format == "json":
                            try: return {"status": "success", "type": "native", "data": resp.json()}
                            except: pass
                        return {"status": "success", "type": "native", "manifest": resp.text}

                # 2. OpenAPI Bridge Route
                elif site_type == "openapi":
                    spec = None
                    for spec_path in ["/openapi.json", "/swagger.json", "/api-docs"]:
                        resp = await client.get(f"{site_url.rstrip('/')}{spec_path}")
                        if resp.status_code == 200:
                            try: spec = resp.json()
                            except: spec = yaml.safe_load(resp.text)
                            break
                    
                    if spec:
                        parsed = OpenAPIBridge.parse_spec(spec, site_url)
                        if output_format == "json":
                            tool = next((t for t in parsed["tools"] if t["name"] == landmark_id), None)
                            if tool: return {"status": "success", "type": "openapi", "data": map_bridge_tool(tool)}
                        
                        signature = OpenAPIBridge.get_tool_signature(parsed, landmark_id)
                        return {"status": "success", "type": "openapi", "signature": signature}

                # 3. GraphQL Bridge Route
                elif site_type == "graphql":
                    gql_url = site_url if site_url.rstrip('/').endswith('/graphql') else f"{site_url.rstrip('/')}/graphql"
                    resp = await client.post(gql_url, json={"query": GraphQLBridge.INTROSPECTION_QUERY})
                    if resp.status_code == 200:
                        schema_data = resp.json().get("data")
                        parsed = GraphQLBridge.parse_schema(schema_data, gql_url)
                        
                        if output_format == "json":
                            tool = next((t for t in parsed["tools"] if t["name"] == landmark_id), None)
                            if tool: return {"status": "success", "type": "graphql", "data": map_bridge_tool(tool)}
                        
                        return {"status": "success", "type": "graphql", "signature": f"// GraphQL Tool: {landmark_id}"}

            except Exception as e:
                logger.error(f"Inspection error for {site_type}: {e}")

        return {"status": "error", "message": f"Inspection failed for {site_type} at {site_url}"}
