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
        manager = AIProtocolManager(
            instructions=f"Bridged Interface for {site_data.get('title', 'External API')}",
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
                manager.landmarks[lm.get("id", lm.get("name"))] = Landmark(**lm)
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
            # Filter landmarks based on security policy
            manager.landmarks = {
                lid: lm for lid, lm in manager.landmarks.items() 
                if security_policy.is_action_allowed(lid)["allowed"]
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
    async def inspect_url(url: str, landmark_id: Optional[str] = None, vault_manager=None, limit: int = 5000, output_format: str = "markdown") -> Dict[str, Any]:
        """Probes a URL for various Elemm interfaces and returns data in requested format."""
        
        headers = {"User-Agent": "ElemmGateway/1.0 (Autonomous Agent)"}
        if vault_manager:
            vault_headers = vault_manager.get_headers(url)
            headers.update(vault_headers)

        async with httpx.AsyncClient(headers=headers) as client:
            # 1. PRIORITY: Check for Native Elemm (Only if NOT a direct spec file)
            is_spec_file = any(url.lower().endswith(ext) for ext in [".json", ".yaml", ".yml"])
            
            try:
                if not is_spec_file:
                    inspect_url = f"{url.rstrip('/')}/.well-known/elemm-manifest.md"
                    params = {"technical": "true", "limit": limit, "full": "true"}
                    if landmark_id: params["landmark_id"] = landmark_id
                    if output_format == "json": params["format"] = "json"
                    
                    resp = await client.get(inspect_url, params=params, follow_redirects=True, timeout=5.0)
                    if resp.status_code == 200:
                        # HEURISTIC: Prevent HTML error pages from being treated as manifests
                        body_sample = resp.text[:500].lower()
                        if "<html" in body_sample or "<!doctype" in body_sample:
                            logger.debug(f"Native probe at {inspect_url} returned HTML, skipping.")
                        else:
                            if output_format == "json":
                                return {"status": "success", "type": "native", "data": resp.json()}
                            return {"status": "success", "type": "native", "manifest": resp.text}
            except: pass

            # 2. Check for GraphQL
            try:
                gql_url = url if url.rstrip('/').endswith('/graphql') else f"{url.rstrip('/')}/graphql"
                probe_resp = await client.post(gql_url, json={"query": GraphQLBridge.INTROSPECTION_QUERY}, timeout=8.0)
                if probe_resp.status_code == 200 and "data" in probe_resp.json():
                    schema_data = probe_resp.json().get("data")
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
            except Exception: pass

            # 3. Check for OpenAPI
            try:
                spec_urls = [f"{url.rstrip('/')}{p}" for p in ["/openapi.json", "/swagger.json", "/api-docs"]]
                if is_spec_file:
                    spec_urls.insert(0, url)
                
                for spec_url in spec_urls:
                    try:
                        resp = await client.get(spec_url, timeout=5.0)
                        if resp.status_code == 200:
                            # Verify it's actually JSON/YAML and not an HTML error page
                            content_sample = resp.text[:500].lower()
                            if "<html" in content_sample or "<!doctype" in content_sample:
                                continue

                            try: spec = resp.json()
                            except: spec = yaml.safe_load(resp.text)
                            
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
                    except Exception: continue
            except Exception: pass

            return {"status": "error", "message": f"Could not find a supported interface at {url}"}

    @classmethod
    async def search_landmarks(cls, url: str, site_data: dict, query: str, limit: int = 100, offset: int = 0, output_format: str = "markdown") -> Union[str, Dict[str, Any]]:
        """Durchsucht Landmarks via Core-Manager-Logik."""
        site_type = site_data.get("type", "native")
        
        if site_type == "native":
            async with httpx.AsyncClient() as client:
                params = {"query": query, "limit": limit, "offset": offset, "format": "json" if output_format == "json" else "markdown"}
                resp = await client.get(f"{url.rstrip('/')}/.well-known/elemm/search", params=params, timeout=10.0)
                return resp.json() if output_format == "json" else resp.text

        # Bridge Search via Transient Manager
        manager = ManifestService._get_transient_manager(site_data)
        res = manager.search_landmarks(query, limit=limit, offset=offset, output_format=output_format)
        return json.loads(res) if output_format == "json" else res

    @staticmethod
    async def inspect_landmark(site_url: str, landmark_id: str, vault_manager=None, limit: int = 5000, offset: int = 0, output_format: str = "markdown", site_type: str = "native", site_data: dict = None) -> Dict[str, Any]:
        """Technische Einsicht via Core-Manager."""
        
        if site_type == "native":
            async with httpx.AsyncClient() as client:
                params = {"landmark_id": landmark_id, "technical": "true", "format": "json" if output_format == "json" else "markdown"}
                resp = await client.get(f"{site_url.rstrip('/')}/.well-known/elemm-manifest.md", params=params)
                if output_format == "json":
                    return {"status": "success", "type": "native", "data": resp.json()}
                return {"status": "success", "type": "native", "manifest": resp.text}

        # Bridge Inspection
        if not site_data: return {"status": "error", "message": "Missing site_data for bridge inspection"}
        manager = ManifestService._get_transient_manager(site_data)
        manifest = manager.get_manifest(landmark_ids=landmark_id, technical=True, output_format=output_format)
        
        if output_format == "json":
            return {"status": "success", "type": site_type, "data": json.loads(manifest)}
        return {"status": "success", "type": site_type, "manifest": manifest}
