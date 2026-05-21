# Copyright (C) 2026 Marc Stöcker
# Website: https://elemm.dev
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

from elemm.core.manager import AIProtocolManager
from elemm.core.models import Landmark

logger = logging.getLogger("elemm-gateway")

class ManifestService:
    """
    Service for probing, parsing, and inspecting Elemm-compliant manifests 
    across Native, OpenAPI, and GraphQL interfaces.
    """
    
    @staticmethod
    def _get_transient_manager(site_data: Dict[str, Any]) -> AIProtocolManager:
        """Erzeugt einen temporären Manager basierend auf Brücken-Daten."""
        instructions = site_data.get("instructions")
        if not instructions:
            info = site_data.get("info")
            if isinstance(info, dict):
                instructions = info.get("x-elemm-instructions")
        if not instructions:
            instructions = f"Bridged Interface for {site_data.get('title', 'External API')}"

        manager = AIProtocolManager(
            instructions=instructions,
            welcome_message=site_data.get("title", "EXTERNAL API")
        )
        # Landmarks registrieren (Unterstützt Objekte und Dicts für Abwärtskompatibilität)
        landmarks = site_data.get("landmarks", site_data.get("tools", []))
        for lm in landmarks:
            if isinstance(lm, dict):
                # Wir konvertieren rohe Brücken-Dicts in offizielle Modelle
                # Falls 'inputSchema' vorhanden ist (OpenAPI), mappen wir es auf 'parameters'
                if "inputSchema" in lm and "parameters" not in lm:
                    from elemm.core.models import Parameter
                    props = lm["inputSchema"].get("properties", {})
                    req = lm["inputSchema"].get("required", [])
                    lm["parameters"] = [
                        Parameter(name=n, type=p.get("type", "string"), description=p.get("description", ""), required=n in req)
                        for n, p in props.items()
                    ]
                if "type" not in lm:
                    if lm.get("is_tool"):
                        lm["type"] = "action"
                    else:
                        lm["type"] = "navigation"
                # Strip out keys that are not part of Landmark/LandmarkMetadata fields to prevent any Pydantic issues
                allowed_keys = {
                    "id", "handler", "tools", "description", "type", "instructions", 
                    "remedy", "parameters", "returns", "response_schema", "tags", "groups", "meta"
                }
                lm_clean = {k: v for k, v in lm.items() if k in allowed_keys}
                if "response_schema" not in lm_clean and "outputSchema" in lm:
                    lm_clean["response_schema"] = lm["outputSchema"]
                manager.landmarks[lm_clean.get("id")] = Landmark(**lm_clean)
            else:
                manager.landmarks[lm.id] = lm
        
        manager._rebuild_hierarchy()
        return manager

    @staticmethod
    def inject_globals(manifest: str, full: bool = False, inject_metadata: bool = True) -> str:
        """Injects gateway globals and appropriate protocol rules."""
        return ManifestBuilder.inject_globals(manifest, full, inject_metadata)

    @staticmethod
    def get_landmarks_summary(site_data: Dict[str, Any], security_policy=None, limit: int = 20) -> str:
        """Nutzt den Core-Manager für die Zusammenfassung mit Sicherheitsfilterung."""
        manager = ManifestService._get_transient_manager(site_data)
        
        if security_policy:
            # Filter landmarks based on security policy, including method checks
            manager.landmarks = {
                lid: lm for lid, lm in manager.landmarks.items() 
                if security_policy.is_action_allowed(
                    lid, 
                    method=lm.meta.get("method") if hasattr(lm, "meta") and isinstance(lm.meta, dict) else (lm.get("meta", {}).get("method") if isinstance(lm, dict) else None)
                )["allowed"]
            }
            # Rebuild hierarchy to ensure tools lists are also filtered
            manager._rebuild_hierarchy()
            
        return manager.get_manifest(max_landmarks=limit)

    @staticmethod
    def normalize_bridge_to_elemm(bridge_data: Dict[str, Any]) -> Dict[str, Any]:
        """Nutzt den Core-Presenter für die Normalisierung."""
        manager = ManifestService._get_transient_manager(bridge_data)
        manifest_json = manager.get_manifest(output_format="json", full=True, max_landmarks=10000)
        return json.loads(manifest_json)

    @staticmethod
    async def fetch_native_manifest(url: str, params: Optional[Dict[str, Any]] = None, vault_manager=None) -> str:
        """Fetches the raw native manifest file from a URL with proper headers and parameters."""
        url = url.strip().rstrip("/")
        if url.endswith("/.well-known/elemm-manifest.md"):
            url = url[:-len("/.well-known/elemm-manifest.md")]
        if vault_manager:
            headers = vault_manager.get_headers(url)
        else:
            headers = {"User-Agent": "ElemmGateway/1.0 (Autonomous Agent)"}

        async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
            resp = await client.get(f"{url}/.well-known/elemm-manifest.md", params=params, timeout=10.0)
            if resp.status_code == 200:
                return resp.text
            raise Exception(f"Error fetching manifest: {resp.text}")

    @staticmethod
    async def inspect_url(url: str, landmark_id: Optional[str] = None, vault_manager=None, limit: int = 5000, output_format: str = "markdown") -> Dict[str, Any]:
        """Probes a URL for various Elemm interfaces with maximum precision."""
        url = url.strip().rstrip("/")
        
        if url.lower().startswith("mcp://") or url.lower() in ["local", "mcp"]:
            from elemm_gateway.services.mcp_config import MCPConfigManager
            from elemm_gateway.services.mcp_bridge import MCPBridge
            import os
            
            mcp_config_path = os.path.expanduser("~/.elemm/mcp_servers.yaml")
            mcp_config = MCPConfigManager(mcp_config_path)
            bridge = MCPBridge(mcp_config)
            
            servers = mcp_config.get_servers()
            landmarks = []
            
            for server_id, server_conf in servers.items():
                try:
                    # Discover landmarks from this local MCP server!
                    server_landmarks = await bridge.discover_landmarks(server_id, vault_manager=vault_manager)
                    
                    # Add the navigation landmark for this server
                    nav_id = f"mcp:{server_id}"
                    landmarks.append({
                        "id": nav_id,
                        "type": "navigation",
                        "description": server_conf.get("description", f"MCP Server {server_id}"),
                        "instructions": server_conf.get("instructions", ""),
                        "tools": [],
                        "meta": {"server_id": server_id}
                    })
                    
                    # Add all tool landmarks
                    for lm in server_landmarks:
                        landmarks.append({
                            "id": lm.id,
                            "type": "action",
                            "name": lm.id,
                            "description": lm.description,
                            "is_tool": True,
                            "isTool": True,
                            "parameters": [
                                {
                                    "name": p.name,
                                    "type": p.type,
                                    "required": p.required,
                                    "description": p.description,
                                    "location": p.location
                                } for p in lm.parameters
                            ] if lm.parameters else [],
                            "returns": getattr(lm, "returns", "any"),
                            "method": getattr(lm, "method", None) or (lm.meta.get("method") if lm.meta else None)
                        })
                except Exception as e:
                    logger.error(f"Error discovering landmarks for {server_id}: {e}")
            
            # Clean up processes in background so we don't block the HTTP response
            import asyncio
            asyncio.create_task(bridge.process_manager.stop_all())
            
            site_data = {
                "landmarks": landmarks,
                "tools": [],
                "title": "Local MCP Environment",
                "type": "native",
                "url": url
            }
            
            if output_format == "json":
                return {
                    "status": "success",
                    "type": "native",
                    "url": url,
                    "data": site_data,
                    "landmarks": landmarks,
                    "tools": []
                }
            return {
                "status": "success",
                "type": "native",
                "url": url,
                "manifest": json.dumps(site_data, indent=2)
            }

        if url.endswith("/.well-known/elemm-manifest.md"):
            url = url[:-len("/.well-known/elemm-manifest.md")]
        if vault_manager:
            headers = vault_manager.get_headers(url)
        else:
            headers = {"User-Agent": "ElemmGateway/1.0 (Autonomous Agent)"}

        async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
            # --- 1. PRIORITY: TRY NATIVE ELEMM PROTOCOL ---
            try:
                inspect_url = f"{url}/.well-known/elemm-manifest.md"
                params = {"technical": "true", "limit": limit, "full": "true"}
                if landmark_id: params["landmark_id"] = landmark_id
                if output_format == "json": params["format"] = "json"
                
                resp = await client.get(inspect_url, params=params, timeout=5.0)
                if resp.status_code == 200:
                    body_sample = resp.text[:500].lower()
                    if not ("<html" in body_sample or "<!doctype" in body_sample):
                        if output_format == "json":
                            return {"status": "success", "type": "native", "data": resp.json()}
                        return {"status": "success", "type": "native", "manifest": resp.text}
            except: pass

            # --- 2. PROBE THE EXACT USER-PROVIDED URL DIRECTLY ---
            # A. Test if the exact URL is a GraphQL Endpoint (using lightweight query)
            try:
                probe_resp = await client.post(url, json={"query": "query { __typename }"}, timeout=5.0)
                if probe_resp.status_code == 200:
                    try:
                        probe_json = probe_resp.json()
                        if isinstance(probe_json, dict) and ("data" in probe_json or "errors" in probe_json):
                            # YES! 100% GraphQL Endpoint! Now do the full introspection:
                            full_resp = await client.post(url, json={"query": GraphQLBridge.INTROSPECTION_QUERY}, timeout=10.0)
                            schema_data = full_resp.json().get("data")
                            parsed = GraphQLBridge.parse_schema(schema_data, url)
                            site_data = {
                                "landmarks": parsed.get("landmarks", []), 
                                "tools": parsed.get("tools", []),
                                "title": f"GraphQL: {url}"
                            }
                            manager = ManifestService._get_transient_manager(site_data)
                            return {
                                "status": "success", "type": "graphql", "url": url, 
                                "manifest": manager.get_manifest(landmark_ids=landmark_id, limit=limit), 
                                "data": ManifestService.normalize_bridge_to_elemm(site_data),
                                "landmarks": parsed.get("landmarks", []),
                                "tools": parsed.get("tools", [])
                            }
                    except: pass
            except: pass

            # B. Test if the exact URL is an OpenAPI Spec (JSON or YAML)
            try:
                resp = await client.get(url, timeout=5.0)
                if resp.status_code == 200:
                    content_sample = resp.text[:500].lower()
                    if not ("<html" in content_sample or "<!doctype" in content_sample):
                        spec = None
                        try: spec = resp.json()
                        except:
                            try: spec = yaml.safe_load(resp.text)
                            except: pass
                        
                        if isinstance(spec, dict) and (spec.get("openapi") or spec.get("swagger")):
                            # YES! 100% OpenAPI spec file!
                            parsed = OpenAPIBridge.parse_spec(spec, url)
                            manager = ManifestService._get_transient_manager(parsed)
                            return {
                                "status": "success", "type": "openapi", "url": url, 
                                "manifest": manager.get_manifest(landmark_ids=landmark_id, limit=limit), 
                                "data": ManifestService.normalize_bridge_to_elemm(parsed),
                                "landmarks": parsed.get("landmarks", []),
                                "tools": parsed.get("tools", [])
                            }
            except: pass

            # --- 3. PATH SCANNING FALLBACKS (GraphQL /graphql) ---
            try:
                if not url.endswith("/graphql"):
                    gql_url = f"{url}/graphql"
                    probe_resp = await client.post(gql_url, json={"query": "query { __typename }"}, timeout=5.0)
                    if probe_resp.status_code == 200:
                        probe_json = probe_resp.json()
                        if isinstance(probe_json, dict) and ("data" in probe_json or "errors" in probe_json):
                            full_resp = await client.post(gql_url, json={"query": GraphQLBridge.INTROSPECTION_QUERY}, timeout=10.0)
                            schema_data = full_resp.json().get("data")
                            parsed = GraphQLBridge.parse_schema(schema_data, gql_url)
                            site_data = {
                                "landmarks": parsed.get("landmarks", []), 
                                "tools": parsed.get("tools", []),
                                "title": f"GraphQL: {gql_url}"
                            }
                            manager = ManifestService._get_transient_manager(site_data)
                            return {
                                "status": "success", "type": "graphql", "url": gql_url, 
                                "manifest": manager.get_manifest(landmark_ids=landmark_id, limit=limit), 
                                "data": ManifestService.normalize_bridge_to_elemm(site_data),
                                "landmarks": parsed.get("landmarks", []),
                                "tools": parsed.get("tools", [])
                            }
            except: pass

            # --- 4. PATH SCANNING FALLBACKS (OpenAPI standard endpoints) ---
            spec_paths = ["/openapi.json", "/swagger.json", "/api-docs"]
            for path in spec_paths:
                spec_url = f"{url}{path}"
                try:
                    resp = await client.get(spec_url, timeout=5.0)
                    if resp.status_code == 200:
                        content_sample = resp.text[:500].lower()
                        if not ("<html" in content_sample or "<!doctype" in content_sample):
                            spec = None
                            try: spec = resp.json()
                            except:
                                try: spec = yaml.safe_load(resp.text)
                                except: pass
                            
                            if isinstance(spec, dict) and (spec.get("openapi") or spec.get("swagger")):
                                parsed = OpenAPIBridge.parse_spec(spec, url)
                                manager = ManifestService._get_transient_manager(parsed)
                                return {
                                    "status": "success", "type": "openapi", "url": spec_url, 
                                    "manifest": manager.get_manifest(landmark_ids=landmark_id, limit=limit), 
                                    "data": ManifestService.normalize_bridge_to_elemm(parsed),
                                    "landmarks": parsed.get("landmarks", []),
                                    "tools": parsed.get("tools", [])
                                }
                except: pass

            return {"status": "error", "message": f"Could not find a supported interface at {url}"}

    @classmethod
    async def search_landmarks(cls, url: str, site_data: dict, query: str, limit: int = 100, offset: int = 0, output_format: str = "markdown", **kwargs) -> Union[str, Dict[str, Any]]:
        """Durchsucht Landmarks via Core-Manager-Logik."""
        site_type = site_data.get("type", "native")
        
        if site_type == "native" and not url.lower().startswith("mcp://"):
            url = url.strip().rstrip("/")
            if url.endswith("/.well-known/elemm-manifest.md"):
                url = url[:-len("/.well-known/elemm-manifest.md")]
            async with httpx.AsyncClient() as client:
                params = {"query": query, "limit": limit, "offset": offset, "format": "json" if output_format == "json" else "markdown"}
                landmark_id = kwargs.get("landmark_id")
                if landmark_id:
                    params["landmark_id"] = landmark_id
                lm_type = kwargs.get("type")
                if lm_type:
                    params["type"] = lm_type
                resp = await client.get(f"{url}/.well-known/elemm/search", params=params, timeout=10.0)
                return resp.json() if output_format == "json" else resp.text

        # Bridge Search via Transient Manager
        manager = ManifestService._get_transient_manager(site_data)
        res = manager.search_landmarks(query, limit=limit, offset=offset, output_format=output_format, **kwargs)
        return json.loads(res) if output_format == "json" else res

    @staticmethod
    async def inspect_landmark(site_url: str, landmark_id: str, vault_manager=None, limit: int = 5000, offset: int = 0, output_format: str = "markdown", site_type: str = "native", site_data: dict = None) -> Dict[str, Any]:
        """Technische Einsicht via Core-Manager."""
        
        if site_type == "native" and not site_url.lower().startswith("mcp://"):
            url = site_url.strip().rstrip("/")
            if url.endswith("/.well-known/elemm-manifest.md"):
                url = url[:-len("/.well-known/elemm-manifest.md")]
            async with httpx.AsyncClient() as client:
                params = {
                    "landmark_id": landmark_id, 
                    "technical": "true", 
                    "format": "json" if output_format == "json" else "markdown",
                    "limit": limit,
                    "offset": offset
                }
                resp = await client.get(f"{url}/.well-known/elemm-manifest.md", params=params)
                if output_format == "json":
                    return {"status": "success", "type": "native", "data": resp.json()}
                return {"status": "success", "type": "native", "manifest": resp.text}

        # Bridge Inspection
        if not site_data: return {"status": "error", "message": "Missing site_data for bridge inspection"}
        manager = ManifestService._get_transient_manager(site_data)
        manifest = manager.get_manifest(
            landmark_ids=landmark_id, 
            technical=True, 
            output_format=output_format,
            max_landmarks=limit,
            offset=offset
        )
        
        if output_format == "json":
            return {"status": "success", "type": site_type, "data": json.loads(manifest)}
        return {"status": "success", "type": site_type, "manifest": manifest}
