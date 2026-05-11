import os
import json
import httpx
import logging
import asyncio
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
import mcp.types as types
from elemm.core.repair import SmartRepairEngine

class ManifestBuilder:
    """Single Source of Truth for Elemm Manifest generation and styling."""
    
    PROTOCOL_RULES = (
        "### 📜 PROTOCOL RULES\n"
        "1. **DISCOVERY**: Use `call_action(action='elemm:get_landmarks')` to see available areas.\n"
        "2. **INSPECTION**: Use `call_action(action='elemm:inspect_landmark', parameters={landmark_id: '...'})` for technical signatures BEFORE execution.\n"
        "3. **HYGIENE (CRITICAL)**: Use `_select` (comma-separated fields), `_filter` (key=val), and `_limit` (number) in EVERY tool call to prevent context overflow.\n"
        "4. **SEQUENCING**: Use the native tool `execute_sequence` for ALL multi-step tasks. It supports piping and aliasing.\n"
        "5. **PIPING**: Use '$alias.field' to pass results between sequence steps. Support deep paths (e.g. `$step0.items[0].id`).\n"
    )

    MEMORY_BANK = (
        "### 🧠 MEMORY BANK (Live Memory)\n"
        "- Use `call_action(action='elemm:list_aliases')` to see stored findings ($step0, $step1, etc.)\n"
        "- PIPING: Chain results via '$alias.path.to.field' (e.g. `$step0.items[0].id`).\n"
        "- ALIASING: Steps auto-alias as '$step0', '$step1'. Use custom 'alias' for clarity.\n"
    )

    GLOBAL_LANDMARKS = (
        "### 🌐 GATEWAY GLOBALS (Virtual Landmarks)\n"
        "> [!NOTE]\n"
        "> These tools are provided by the gateway and are available on ALL sites via `call_action`.\n\n"
        "- **`elemm`**: Global system operations and discovery.\n"
        "  - Tool: `elemm:get_landmarks` -> Returns: Summary of available landmarks\n"
        "  - Tool: `elemm:inspect_landmark` (Params: `landmark_id`) -> Returns: Technical signatures\n"
        "  - Tool: `elemm:list_aliases` -> Returns: Current pipeline state (memory bank)\n"
    )

    @classmethod
    def build_header(cls, title: str, version: str) -> str:
        return f"# 🚀 ELEMM v2 INTERFACE: {title} (v{version})\n\n{cls.PROTOCOL_RULES}\n{cls.MEMORY_BANK}\n{cls.GLOBAL_LANDMARKS}"

    @classmethod
    def inject_globals(cls, manifest: str) -> str:
        """Injects gateway globals and updates legacy hints in an existing manifest."""
        # Cleanup legacy hints
        manifest = manifest.replace("inspect_landmark(id)", "call_action(action='elemm:inspect_landmark', parameters={'landmark_id': '...'})")
        manifest = manifest.replace("'inspect_landmarks'", "'elemm:inspect_landmark'")
        
        # Avoid double injection
        if "GATEWAY GLOBALS" in manifest:
            return manifest
            
        if "### LANDMARK TOPOLOGY" in manifest:
            return manifest.replace("### LANDMARK TOPOLOGY", cls.GLOBAL_LANDMARKS + "\n### LANDMARK TOPOLOGY")
        if "### TECHNICAL SIGNATURES" in manifest:
            return manifest.replace("### TECHNICAL SIGNATURES", cls.GLOBAL_LANDMARKS + "\n### TECHNICAL SIGNATURES")
        return manifest + "\n" + cls.GLOBAL_LANDMARKS

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
        
        if auth_type == "apiKey":
            target = entry.get("in", "query")
            if target == "header":
                headers[name] = val
            else:
                params[name] = val
        elif auth_type == "bearer":
            headers["Authorization"] = f"Bearer {val}"
        elif auth_type == "basic":
            headers["Authorization"] = f"Basic {val}"
        
        logger.info(f"Vault: Applied {auth_type} for {host}")
        return True

    def get_auth_param_names(self, host: str) -> List[str]:
        """Returns names of parameters that this vault can provide for the host."""
        entry = self.get_entry(host)
        if not entry: return []
        if isinstance(entry, str): return ["key"]
        name = entry.get("name", "key")
        return [name]

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

class GraphQLExecutor:
    """Handles generation and execution of GraphQL queries."""
    def __init__(self, vault_manager: VaultManager):
        self.vault = vault_manager

    async def execute(self, tool_data: Dict[str, Any], arguments: Dict[str, Any]) -> str:
        meta = tool_data.get("meta", {})
        base_url = meta.get("base_url", "")
        operation_type = meta.get("operation_type", "query")
        field_name = meta.get("field_name", "")
        
        # Extract hygiene params
        select = arguments.pop("_select", "id") # Default to 'id' if nothing selected
        
        # Construct GQL Query
        # We wrap arguments into GQL variables
        var_defs = []
        var_values = {}
        arg_calls = []
        
        for k, v in arguments.items():
            var_name = f"var_{k}"
            # Use original GQL type if available in metadata, else guess
            prop_meta = tool_data.get("inputSchema", {}).get("properties", {}).get(k, {})
            g_type = prop_meta.get("gql_type")
            
            if not g_type:
                if isinstance(v, bool): g_type = "Boolean!"
                elif isinstance(v, int): g_type = "Int!"
                elif isinstance(v, float): g_type = "Float!"
                else: g_type = "String!"
            
            var_defs.append(f"${var_name}: {g_type}")
            var_values[var_name] = v
            arg_calls.append(f"{k}: ${var_name}")

        arg_str = f"({', '.join(arg_calls)})" if arg_calls else ""
        var_def_str = f"({', '.join(var_defs)})" if var_defs else ""
        
        # Build selection set from _select (supporting nested fields like 'name, info.id')
        selection_set = self._build_selection_set(select)
        
        query = f"{operation_type} ElemmQuery{var_def_str} {{ {field_name}{arg_str} {selection_set} }}"
        
        # Prepare Request
        headers = {"User-Agent": "Elemm-Gateway/2.0", "Content-Type": "application/json"}
        params = {}
        host_key = urlparse(base_url).netloc
        self.vault.apply_auth(host_key, params, headers)

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    base_url,
                    json={"query": query, "variables": var_values},
                    headers=headers,
                    params=params,
                    timeout=30.0
                )
                
                res_json = {}
                try:
                    res_json = resp.json()
                except:
                    pass

                if "errors" in res_json or resp.status_code != 200:
                    debug_echo = {
                        "url": base_url,
                        "query": query,
                        "variables": var_values
                    }
                    
                    # SmartRepair: Translate common GQL errors
                    errors = res_json.get("errors", [])
                    error_msg = errors[0].get("message", "") if errors else resp.text
                    
                    repair = SmartRepairEngine.handle_remote_error(resp.status_code, error_msg)
                    
                    # Map HTTP errors if applicable, else use GQL default
                    status_map = {
                        401: "AUTHENTICATION_FAILED",
                        403: "ACCESS_DENIED",
                        429: "RATE_LIMIT_EXCEEDED",
                        500: "SERVER_ERROR"
                    }
                    protocol_error = status_map.get(resp.status_code, "GRAPHQL_ERROR")
                    remedy = repair.remedy
                    
                    if "must have a selection of subfields" in error_msg:
                        field_match = re.search(r'Field "(.*?)"', error_msg)
                        target = field_match.group(1) if field_match else "the field"
                        remedy = f"Field '{target}' is an object/interface. You MUST specify sub-fields in '_select' using dot-notation (e.g. '{target}.id' or '{target}.name')."
                        protocol_error = "NESTING_REQUIRED"
                    elif "Variable" in error_msg and "expecting type" in error_msg:
                        remedy = "Type mismatch in variables. Ensure IDs are strings and follow the technical signature exactly."
                        protocol_error = "TYPE_MISMATCH"

                    return json.dumps({
                        "status": "error",
                        "_PROTOCOL_ERROR": protocol_error,
                        "message": repair.message,
                        "remedy": remedy,
                        "http_code": resp.status_code,
                        "raw_errors": errors,
                        "_DEBUG_ECHO": debug_echo
                    }, indent=2)
                
                # Unbox GQL 'data' field
                data = res_json.get("data", {}).get(field_name, res_json.get("data"))
                return json.dumps(data, indent=2)

        except Exception as e:
            return f"Error executing GraphQL call: {str(e)}"

    def _build_selection_set(self, select: str) -> str:
        """Converts comma-separated fields to a GQL selection set."""
        fields = [f.strip() for f in select.split(",")]
        root = {}
        for f in fields:
            parts = f.split(".")
            curr = root
            for p in parts:
                if p not in curr: curr[p] = {}
                curr = curr[p]
        
        return self._dict_to_gql(root)

    def _dict_to_gql(self, d: Dict) -> str:
        if not d: return ""
        inner = []
        for k, v in d.items():
            sub = self._dict_to_gql(v)
            inner.append(f"{k} {sub}" if sub else k)
        return f"{{ {', '.join(inner)} }}"

class OpenAPIExecutor:
    """Handles the heavy lifting of executing OpenAPI requests."""
    def __init__(self, vault_manager: VaultManager):
        self.vault = vault_manager

    async def execute(self, tool_data: Dict[str, Any], arguments: Dict[str, Any]) -> str:
        meta = tool_data.get("meta", {})
        base_url = meta.get("base_url", "")
        path = meta.get("path", "")
        method = meta.get("method", "GET").upper()
        
        # Extract hygiene params
        select = arguments.pop("_select", None)
        filter_str = arguments.pop("_filter", None)
        limit = arguments.pop("_limit", None)

        # Pre-Validation: Catch missing required fields locally (Agent Guidance)
        required_fields = tool_data.get("inputSchema", {}).get("required", [])
        
        # Exclude fields provided by the vault
        host_key = urlparse(base_url).netloc
        vault_provided = self.vault.get_auth_param_names(host_key)
        
        missing = [f for f in required_fields if f not in arguments and f not in vault_provided]
        if missing:
            return json.dumps({
                "status": "error",
                "_PROTOCOL_ERROR": "VALIDATION_FAILED",
                "message": f"Local Validation Failed: Missing required parameters {missing}",
                "remedy": f"The tool '{tool_data.get('name')}' requires these fields: {required_fields}. Check technical signatures with 'elemm:inspect_landmark'.",
                "_DEBUG_ECHO": {
                    "tool": tool_data.get("name"),
                    "received_params": list(arguments.keys()),
                    "missing_params": missing,
                    "vault_aware": True
                }
            }, indent=2)

        # Prepare request
        full_url = f"{base_url}{path}"
        params = {}
        headers = {"User-Agent": "Elemm-Gateway/2.0"}
        json_body = None

        # Map arguments to path/query/body
        for param_meta in meta.get("params", []):
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
                
                # Unified Error Handling with Forensics
                if resp.status_code != 200:
                    debug_echo = {
                        "method": method,
                        "url": str(resp.url),
                        "sent_params": params,
                        "sent_body_preview": str(json_body)[:200] if json_body else None
                    }
                    
                    # Extract error details
                    error_data = {}
                    try: error_data = resp.json()
                    except: pass
                    error_msg = error_data.get("error", {}).get("message") or error_data.get("message") or resp.text
                    
                    status_map = {
                        400: "BAD_REQUEST",
                        401: "AUTHENTICATION_FAILED",
                        403: "ACCESS_DENIED",
                        404: "NOT_FOUND",
                        422: "VALIDATION_FAILED",
                        429: "RATE_LIMIT_EXCEEDED",
                        500: "SERVER_ERROR"
                    }
                    
                    protocol_error = status_map.get(resp.status_code, "REMOTE_ERROR")
                    repair = SmartRepairEngine.handle_remote_error(resp.status_code, error_msg)
                    
                    return json.dumps({
                        "status": "error",
                        "_PROTOCOL_ERROR": protocol_error,
                        "message": repair.message,
                        "remedy": repair.remedy,
                        "remote_response": error_msg,
                        "_DEBUG_ECHO": debug_echo
                    }, indent=2)

                data = resp.json()
                
                # Apply Hygiene
                data = ResponseSquisher.squish(data, select, filter_str)
                if limit and isinstance(data, list):
                    data = data[:int(limit)]
                
                # Empty Result Guiding
                if not data or (isinstance(data, list) and len(data) == 0):
                    return json.dumps({
                        "status": "success",
                        "data": data,
                        "_INFO": "The call was successful but returned no results. Broaden your search/filter if this was unexpected."
                    }, indent=2)
                    
                return json.dumps(data, indent=2)

        except Exception as e:
            return json.dumps({
                "status": "error",
                "message": f"Execution failed: {str(e)}",
                "remedy": "Check your connection and the technical signature of the landmark."
            }, indent=2)

class SequenceEngine:
    """Orchestrates multi-step tool executions with piping and aliasing."""
    def __init__(self, gateway: Any):
        self.gateway = gateway
        self.aliases = {}

    def list_aliases(self) -> Dict[str, Any]:
        """Returns all currently stored aliases."""
        return self.aliases

    async def execute(self, actions: List[Dict[str, Any]] = None, **kwargs) -> List[types.TextContent]:
        # Support both 'actions' (protocol) and 'steps' (LLM intuition)
        actions = actions or kwargs.get("steps", [])
        if not actions:
            return [types.TextContent(type="text", text="Error: No actions or steps provided in sequence.")]
            
        results = []
        for i, step in enumerate(actions):
            action_id = step.get("action")
            params = step.get("parameters", {})
            alias = step.get("alias")

            # 1. Resolve Piping ($alias.field)
            resolved_params = self._resolve_piping(params)

            # 2. Execute Action
            if action_id.startswith("elemm:"):
                result_val = await self.gateway._execute_single(action_id, resolved_params)
            elif action_id in ["get_manifest", "get_landmarks", "inspect_landmark"]:
                tool_results = await self.gateway._proxy_core_tool(action_id, resolved_params)
                result_val = tool_results[0].text
            else:
                result_val = await self.gateway._execute_single(action_id, resolved_params)

            # 3. Store Alias (Explicit & Automatic)
            try:
                final_res = json.loads(result_val)
            except:
                final_res = result_val

            self.aliases[f"step{i}"] = final_res
            if alias:
                self.aliases[alias] = final_res

            results.append({
                "step": i,
                "action": action_id,
                "alias": alias or f"step{i}",
                "result": final_res
            })

        return [types.TextContent(type="text", text=json.dumps(results, indent=2))]

    def _resolve_piping(self, params: Any) -> Any:
        if isinstance(params, str) and params.startswith("$"):
            import re
            # Extract alias and path: $alias.field.subfield or $alias[0].field
            match = re.match(r"\$([\w\d]+)(.*)", params)
            if match:
                alias_name, path = match.groups()
                if alias_name in self.aliases:
                    val = self.aliases[alias_name]
                    if not path:
                        return val
                    # Deep navigation
                    return self._navigate(val, path)
            return params
        
        if isinstance(params, dict):
            return {k: self._resolve_piping(v) for k, v in params.items()}
        
        if isinstance(params, list):
            return [self._resolve_piping(item) for item in params]
            
        return params

    def _navigate(self, data: Any, path: str) -> Any:
        import re
        from elemm.core.repair import SmartRepairEngine
        
        # Path might start with . or [
        parts = re.split(r"\.|(?=\[)", path)
        curr = data
        for p in parts:
            if not p: continue
            try:
                if p.startswith("["):
                    idx = int(p[1:-1])
                    curr = curr[idx]
                else:
                    curr = curr[p]
            except Exception:
                # Use SmartRepair for better error messages
                available_keys = list(curr.keys()) if isinstance(curr, dict) else []
                repair = SmartRepairEngine.handle_piping_failure(
                    alias="current", # Could be improved to track actual alias
                    field=p,
                    available_keys=available_keys[:10] # Limit to 10 for tokens
                )
                return f"{{{{PROTOCOL_ERROR: {repair.message} REMEDY: {repair.remedy}}}}}"
        return curr
