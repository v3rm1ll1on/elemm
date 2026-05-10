import os
import json
import httpx
import logging
import asyncio
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
import mcp.types as types

logger = logging.getLogger("elemm-gateway")

class VaultManager:
    """Handles API key management and injection."""
    def __init__(self, vault_path: str):
        self.vault_path = vault_path
        self.vault = self.load()

    def load(self) -> Dict[str, Any]:
        if not os.path.exists(self.vault_path):
            return {}
        try:
            with open(self.vault_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Vault: Failed to load from {self.vault_path}: {e}")
            return {}

    def get_entry(self, host: str) -> Optional[Dict[str, Any]]:
        return self.vault.get(host)

    def apply_auth(self, host: str, params: Dict[str, Any], headers: Dict[str, Any]):
        entry = self.get_entry(host)
        if not entry:
            return False
            
        # Handle simple string entries (legacy/shorthand support)
        if isinstance(entry, str):
            params["key"] = entry
            logger.info(f"Vault: Applied simple apiKey for {host}")
            return True

        if not isinstance(entry, dict):
            logger.warning(f"Vault: Entry for {host} is not a dict or string.")
            return False

        auth_type = entry.get("type", "apiKey")
        name = entry.get("name", "key")
        val = entry.get("value", "")
        location = entry.get("in", "query")

        if auth_type == "apiKey":
            if location == "query":
                params[name] = val
            else:
                headers[name] = val
        elif auth_type == "bearer":
            headers["Authorization"] = f"Bearer {val}"
        elif auth_type == "basic":
            headers["Authorization"] = f"Basic {val}"
        
        logger.info(f"Vault: Applied {auth_type} for {host}")
        return True

class ResponseSquisher:
    """Handles context hygiene by filtering JSON responses."""
    @staticmethod
    def squish(data: Any, select: Optional[str] = None, filter_str: Optional[str] = None) -> Any:
        if not data:
            return data
            
        # 1. Filter by key=val
        if filter_str and "=" in filter_str and isinstance(data, list):
            k, v = filter_str.split("=", 1)
            data = [item for item in data if str(item.get(k)) == v]
        
        # 2. Select fields (nested)
        if select:
            fields = [f.strip() for f in select.split(",")]
            if isinstance(data, list):
                data = [ResponseSquisher._pick_fields(item, fields) for item in data]
            else:
                data = ResponseSquisher._pick_fields(data, fields)
                
        return data

    @staticmethod
    def _pick_fields(obj: Any, fields: List[str]) -> Dict[str, Any]:
        if not isinstance(obj, dict):
            return obj
        res = {}
        for f in fields:
            if "." in f:
                parts = f.split(".", 1)
                if parts[0] in obj:
                    nested_val = ResponseSquisher._pick_fields(obj[parts[0]], [parts[1]])
                    if parts[0] not in res:
                        res[parts[0]] = {}
                    if isinstance(res[parts[0]], dict) and isinstance(nested_val, dict):
                        res[parts[0]].update(nested_val)
                    else:
                        res[parts[0]] = nested_val
            elif f in obj:
                res[f] = obj[f]
        return res

class OpenAPIExecutor:
    """Handles the heavy lifting of executing OpenAPI requests."""
    def __init__(self, vault_manager: VaultManager):
        self.vault = vault_manager

    async def execute(self, tool_meta: Dict[str, Any], arguments: Dict[str, Any]) -> str:
        base_url = tool_meta.get("base_url", "")
        path = tool_meta.get("path", "")
        method = tool_meta.get("method", "GET").upper()
        
        # Extract hygiene params
        select = arguments.pop("_select", None)
        filter_str = arguments.pop("_filter", None)
        limit = arguments.pop("_limit", None)

        # Prepare request
        full_url = f"{base_url}{path}"
        params = {}
        headers = {"User-Agent": "Elemm-Gateway/2.0"}
        json_body = None

        # Map arguments to path/query/body
        for param_meta in tool_meta.get("params", []):
            p_name = param_meta["name"]
            p_in = param_meta["in"]
            if p_name in arguments:
                val = arguments[p_name]
                if p_in == "path":
                    full_url = full_url.replace(f"{{{p_name}}}", str(val))
                elif p_in == "query":
                    params[p_name] = val
                elif p_in == "header":
                    headers[p_name] = val
                elif p_in == "body":
                    json_body = val

        # Apply Auth
        host_key = urlparse(base_url).netloc
        self.vault.apply_auth(host_key, params, headers)

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.request(
                    method, 
                    full_url, 
                    params=params, 
                    headers=headers, 
                    json=json_body, 
                    follow_redirects=True,
                    timeout=30.0
                )
                
                if resp.status_code in [401, 403]:
                    return json.dumps({
                        "status": "error",
                        "_PROTOCOL_ERROR": "AUTHENTICATION_FAILED",
                        "message": f"The remote server ({host_key}) rejected the request due to authentication issues (HTTP {resp.status_code}).",
                        "remedy": f"Add the correct API key for '{host_key}' to your local ~/.elemm/vault.json file.",
                        "instruction": f"The user needs to provide an API key for '{host_key}'. Please explain that this key should be placed in ~/.elemm/vault.json."
                    }, indent=2)
                
                if resp.status_code != 200:
                    return f"Error: Remote API returned HTTP {resp.status_code}\n{resp.text}"

                data = resp.json()
                
                # Apply Hygiene
                data = ResponseSquisher.squish(data, select, filter_str)
                if limit and isinstance(data, list):
                    data = data[:int(limit)]
                    
                return json.dumps(data, indent=2)

        except Exception as e:
            return f"Error executing OpenAPI call: {str(e)}"

class SequenceEngine:
    """Orchestrates multi-step tool executions with piping and aliasing."""
    def __init__(self, gateway: Any):
        self.gateway = gateway
        self.aliases = {}

    async def execute(self, actions: List[Dict[str, Any]]) -> List[types.TextContent]:
        results = []
        for i, step in enumerate(actions):
            action_id = step.get("action")
            params = step.get("parameters", {})
            alias = step.get("alias")

            # 1. Resolve Piping ($alias.field)
            resolved_params = self._resolve_piping(params)

            # 2. Execute Action
            # Core tools vs OpenAPI tools
            if action_id in ["get_manifest", "get_landmarks", "inspect_landmark"]:
                # Core tools are proxied via the gateway instance
                tool_results = await self.gateway._proxy_core_tool(action_id, resolved_params)
                result_val = tool_results[0].text
            else:
                # API actions
                result_val = await self.gateway._execute_openapi(action_id, resolved_params)

            # 3. Store Alias
            if alias:
                try:
                    self.aliases[alias] = json.loads(result_val)
                except:
                    self.aliases[alias] = result_val

            # 4. Append Result (try to parse as JSON for cleaner output)
            try:
                final_res = json.loads(result_val)
            except:
                final_res = result_val

            results.append({
                "step": i,
                "action": action_id,
                "alias": alias,
                "result": final_res
            })

        return [types.TextContent(type="text", text=json.dumps(results, indent=2))]

    def _resolve_piping(self, params: Any) -> Any:
        if isinstance(params, str) and params.startswith("$"):
            parts = params[1:].split(".", 1)
            alias_name = parts[0]
            if alias_name in self.aliases:
                val = self.aliases[alias_name]
                if len(parts) > 1 and isinstance(val, dict):
                    return val.get(parts[1], params)
                return val
            return params
        
        if isinstance(params, dict):
            return {k: self._resolve_piping(v) for k, v in params.items()}
        
        if isinstance(params, list):
            return [self._resolve_piping(item) for item in params]
            
        return params
