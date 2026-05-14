import httpx
import json
import yaml
import logging
from urllib.parse import urlparse
from typing import Dict, Any, Optional

from .openapi_bridge import OpenAPIBridge
from .graphql_bridge import GraphQLBridge

logger = logging.getLogger(__name__)

class ManifestService:
    """
    A standalone service to probe and generate Elemm manifests from various sources.
    Used by both the Gateway and the Dashboard.
    """
    
    @staticmethod
    async def inspect_url(url: str, landmark_id: Optional[str] = None, vault_manager=None) -> Dict[str, Any]:
        """
        Probes a URL for OpenAPI, GraphQL, or Native Elemm interfaces and returns the manifest.
        Can optionally fetch a specific landmark's sub-manifest.
        """
        async with httpx.AsyncClient() as client:
            # 1. Check for GraphQL
            try:
                # Add headers from vault if available
                headers = {}
                if vault_manager:
                    host = urlparse(url).netloc
                    auth = vault_manager.get_auth(host)
                    if auth:
                        # Simplified auth application for probing
                        if auth['type'] == 'apiKey' and auth['in'] == 'header':
                            headers[auth['name']] = auth['value']
                        elif auth['type'] == 'bearer':
                            headers['Authorization'] = f"Bearer {auth['value']}"

                resp = await client.post(url, json={"query": "{ __schema { types { name } } }"}, headers=headers, timeout=5.0)
                if resp.status_code == 200 and "data" in resp.json():
                    spec = resp.json()
                    schema_data = spec.get("data")
                    parsed = GraphQLBridge.parse_schema(schema_data, url)
                    
                    if landmark_id:
                        manifest = GraphQLBridge.get_tool_signature(parsed, landmark_id)
                        
                        # INJECT TECHNICAL DISCOVERY JSON
                        tools = parsed.get("tools", [])
                        relevant_tools = [t for t in tools if t["name"] == landmark_id or t["name"].startswith(f"{landmark_id}:")]
                        if relevant_tools:
                            manifest += "\n\n### TECHNICAL DISCOVERY\n```json-elemm\n"
                            manifest += json.dumps(relevant_tools, indent=2)
                            manifest += "\n```"
                    else:
                        manifest = GraphQLBridge.generate_virtual_manifest(parsed)
                        
                    return {
                        "type": "graphql",
                        "manifest": manifest,
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
                        try:
                            spec = resp.json()
                        except:
                            spec = yaml.safe_load(resp.text)

                        if isinstance(spec, dict) and ("openapi" in spec or "swagger" in spec):
                            parsed = OpenAPIBridge.parse_spec(spec, url.rsplit("/", 1)[0])
                            
                            # Use summary for root, or signature for specific landmark
                            if landmark_id:
                                manifest = OpenAPIBridge.get_tool_signature(parsed, landmark_id)
                                
                                # INJECT TECHNICAL DISCOVERY JSON
                                tools = parsed.get("tools", [])
                                relevant_tools = [t for t in tools if t["name"] == landmark_id or t["name"].startswith(f"{landmark_id}:")]
                                if relevant_tools:
                                    manifest += "\n\n### TECHNICAL DISCOVERY\n```json-elemm\n"
                                    manifest += json.dumps(relevant_tools, indent=2)
                                    manifest += "\n```"
                            else:
                                manifest = OpenAPIBridge.generate_virtual_manifest(parsed)
                                
                            return {
                                "type": "openapi",
                                "manifest": manifest,
                                "tools": parsed.get("tools", []),
                                "url": url,
                                "status": "success"
                            }
                except: pass

            # 3. Native Elemm
            manifest_url = f"{url.rstrip('/')}/.well-known/elemm-manifest.md"
            params = {}
            if landmark_id:
                params["landmark_id"] = landmark_id
                params["technical"] = "true"

            try:
                resp = await client.get(manifest_url, params=params, timeout=10.0, follow_redirects=True)
                if resp.status_code == 200:
                    return {
                        "type": "native",
                        "manifest": resp.text,
                        "url": url,
                        "landmark_id": landmark_id,
                        "status": "success"
                    }
            except: pass

            return {
                "status": "error",
                "message": f"Could not find a supported interface at {url}"
            }

    @staticmethod
    async def inspect_landmark(url: str, landmark_id: str, vault_manager=None) -> Dict[str, Any]:
        """
        Fetches the technical signature/manifest for a specific landmark or tool.
        Supports Native Elemm, OpenAPI, and GraphQL via unified detection.
        """
        # Re-use the inspection logic which already handles landmark-specific detailed manifests
        res = await ManifestService.inspect_url(url, landmark_id=landmark_id, vault_manager=vault_manager)
        
        if res.get("status") == "success":
            # Extract the manifest as the 'signature' for the debugger
            return {
                "status": "success", 
                "signature": res.get("manifest"),
                "type": res.get("type")
            }
            
        return res
        """
        Fetches the technical signature for a specific landmark from a native Elemm site.
        """
        async with httpx.AsyncClient() as client:
            # For now, we assume the site follows the standard inspect_landmark pattern
            # In a real scenario, this would be an action call. 
            # For the debugger, we try to fetch it via a standard path if available 
            # or simulate the gateway action.
            
            # 1. Try to fetch from the manifest if we can get the full one
            # (In this prototype, we'll just return a mock or try to probe)
            
            # Actually, most native sites might have a /elemm/inspect?landmark=... endpoint
            # or we just fetch the full manifest and extract it.
            
            manifest_url = f"{url.rstrip('/')}/.well-known/elemm-manifest.md"
            try:
                resp = await client.get(manifest_url, timeout=10.0)
                if resp.status_code == 200:
                    manifest_text = resp.text
                    signatures_index = manifest_text.indexOf('### TECHNICAL SIGNATURES') if hasattr(manifest_text, 'indexOf') else manifest_text.find('### TECHNICAL SIGNATURES')
                    if signatures_index != -1:
                        import re
                        sig_section = manifest_text[signatures_index:]
                        # Look for the signature block
                        pattern = rf"Tool: {re.escape(landmark_id)}.*?function call_action\(action: '{re.escape(landmark_id)}'.*?\);"
                        match = re.search(pattern, sig_section, re.DOTALL)
                        if match:
                            return {"status": "success", "signature": match.group(0)}
            except: pass

            return {
                "status": "error",
                "message": f"Could not find signature for landmark '{landmark_id}' at {url}"
            }
