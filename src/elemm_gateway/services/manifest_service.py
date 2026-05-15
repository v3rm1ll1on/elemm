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
from typing import Dict, Any, List, Optional

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
    async def inspect_url(url: str, landmark_id: Optional[str] = None, vault_manager=None, limit: int = 20) -> Dict[str, Any]:
        """Probes a URL for various Elemm interfaces."""
        async with httpx.AsyncClient() as client:
            headers = {}
            if vault_manager:
                headers = vault_manager.get_headers(url)

            # 1. Check for GraphQL
            try:
                resp = await client.post(url, json={"query": GraphQLBridge.INTROSPECTION_QUERY}, headers=headers, timeout=5.0)
                if resp.status_code == 200 and "data" in resp.json():
                    schema_data = resp.json().get("data")
                    parsed = GraphQLBridge.parse_schema(schema_data, url)
                    return {
                        "type": "graphql",
                        "manifest": GraphQLBridge.generate_virtual_manifest(parsed, limit=limit),
                        "tools": parsed.get("tools", []),
                        "url": url,
                        "status": "success"
                    }
            except: pass

            # 2. Check for OpenAPI
            if any(url.endswith(ext) for ext in [".json", ".yaml", ".yml"]) or "/openapi" in url:
                try:
                    resp = await client.get(url, follow_redirects=True, timeout=10.0)
                    if resp.status_code == 200:
                        try: spec = resp.json()
                        except: spec = yaml.safe_load(resp.text)

                        if isinstance(spec, dict) and ("openapi" in spec or "swagger" in spec):
                            parsed = OpenAPIBridge.parse_spec(spec, url.rsplit("/", 1)[0])
                            return {
                                "type": "openapi",
                                "manifest": OpenAPIBridge.generate_virtual_manifest(parsed, limit=limit),
                                "tools": parsed.get("tools", []),
                                "url": url,
                                "status": "success"
                            }
                except: pass

            # 3. Native Elemm
            manifest_url = f"{url.rstrip('/')}/.well-known/elemm-manifest.md"
            try:
                resp = await client.get(manifest_url, timeout=10.0, follow_redirects=True)
                if resp.status_code == 200:
                    return {
                        "type": "native",
                        "manifest": resp.text,
                        "url": url,
                        "status": "success"
                    }
            except: pass

            return {"status": "error", "message": f"Could not find a supported interface at {url}"}

    @staticmethod
    def get_landmarks_summary(site_data: Dict[str, Any], security_policy: Optional[Any] = None, limit: int = 20) -> str:
        """Returns a high-level summary of available landmarks for a site."""
        m_type = site_data.get("type")
        manifest = site_data.get("manifest", "")
        tools = site_data.get("tools", [])
        
        res = "### LANDMARK TOPOLOGY\n"
        
        discovered = []
        if m_type == "native":
            # Extract from markdown manifest
            matches = re.findall(r"- \*\*`(.*?)`\*\*: (.*?)\n", manifest)
            for lid, desc in sorted(matches):
                if lid == "elemm": continue
                if security_policy and not security_policy.is_action_allowed(f"{lid}_inspect")["allowed"]:
                    continue
                discovered.append((lid, desc))
        else:
            # Aggregate from OpenAPI/GraphQL tools
            landmarks = {}
            for t in tools:
                lm = t["name"].split(":")[0] if ":" in t["name"] else t["name"].split("_", 1)[0]
                if security_policy and not security_policy.is_action_allowed(f"{lm}_inspect")["allowed"]:
                    continue
                landmarks[lm] = landmarks.get(lm, 0) + 1
            for lm, count in sorted(landmarks.items()):
                discovered.append((lm, f"({count} tools)"))
        
        # Apply Structural Truncation
        visible = discovered[:limit]
        remaining = len(discovered) - limit
        
        for lid, info in visible:
            res += f"- **{lid}**: {info}\n"
            
        if remaining > 0:
            res += f"\n- (... and {remaining} more landmarks available. Use `get_manifest(landmark_id=\"...\")` with a specific ID to explore other areas.)"
        
        return ManifestBuilder.inject_globals(res)

    @staticmethod
    async def inspect_landmark(site_url: str, site_data: Dict[str, Any], landmark_ids: List[str], limit: int = 20) -> str:
        """Generates technical signatures for specific landmarks."""
        m_type = site_data.get("type")
        tools = site_data.get("tools", [])
        
        signatures = []
        
        if m_type == "native":
            async with httpx.AsyncClient() as client:
                for tid in landmark_ids:
                    inspect_url = f"{site_url.rstrip('/')}/.well-known/elemm-manifest.md"
                    try:
                        resp = await client.get(inspect_url, params={"landmark_id": tid, "technical": "true", "limit": limit}, follow_redirects=True)
                        if resp.status_code == 200:
                            content = resp.text
                            if "```json-elemm" in content:
                                content = content.split("```json-elemm")[0].strip()
                            signatures.append(content)
                    except: pass
            final_md = "\n\n".join(signatures)
            return ManifestBuilder.inject_globals(final_md, inject_metadata=False)
        else:
            # Generate TS signatures for OpenAPI/GraphQL
            total_relevant = 0
            for tid in landmark_ids:
                relevant_tools = [t for t in tools if t["name"] == tid or t["name"].startswith(f"{tid}:") or t["name"].startswith(f"{tid}_")]
                total_relevant += len(relevant_tools)
                
                for t in relevant_tools[:limit]:
                    props = t['inputSchema'].get('properties', {})
                    required = t['inputSchema'].get('required', [])
                    
                    sig = f"/**\n * Tool: {t['name']}\n * Description: {t['description']}\n"
                    params_list = []
                    for p_name, p_schema in props.items():
                        if p_name.startswith("_"): continue
                        p_type = p_schema.get('type', 'any')
                        p_desc = p_schema.get('description', '')
                        req_mark = "[REQUIRED]" if p_name in required else "[OPTIONAL]"
                        sig += f" * @param {p_name} ({p_type}) {req_mark} {p_desc}\n"
                        opt = "" if p_name in required else "?"
                        params_list.append(f"{p_name}{opt}: {p_type}")
                    sig += " */\n"
                    sig += f"function call_action(action: '{t['name']}', parameters: {{ {', '.join(params_list)} }}): any;\n"
                    signatures.append(sig)
            
            if not signatures:
                return f"No tools found for landmark/id '{landmark_ids}'."
            
            content = "### TECHNICAL SIGNATURES\n```typescript\n" + "\n\n".join(signatures) + "\n```\n"
            
            if total_relevant > len(signatures):
                content += f"\n\n(... and {total_relevant - len(signatures)} more tools in this area were truncated to fit the inspection limit. Use more specific filters if possible.)"

            return ManifestBuilder.inject_globals(content, inject_metadata=False)
