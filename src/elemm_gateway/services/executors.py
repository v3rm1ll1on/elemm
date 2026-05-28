# Copyright (C) 2026 Marc Stöcker
# Website: https://elemm.dev
#
# This program is licensed under the Business Source License 1.1 (BSL 1.1).
# See the LICENSE file in the root directory for details.

import json
import httpx
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from elemm.core.repair import SmartRepairEngine
from .vault import VaultManager
from .hygiene import ResponseSquisher


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
        if isinstance(select, list):
            select = ",".join(select)
            
        limit = arguments.pop("_limit", None)
        offset = arguments.pop("_offset", None)
        
        if limit: limit = int(limit)
        if offset: offset = int(offset)
        
        # ... (GQL construction logic) ...
        var_defs = []
        var_values = {}
        arg_calls = []
        
        for k, v in arguments.items():
            var_name = f"var_{k}"
            prop_meta = tool_data.get("inputSchema", {}).get("properties", {}).get(k, {})
            g_type = prop_meta.get("gql_type")
            
            # Fallback: gql_type direkt aus der parameters-Liste lesen (wenn inputSchema fehlt,
            # z.B. wenn tool_data vom Pydantic-Konvertierungsblock ohne inputSchema gebaut wurde)
            if not g_type:
                for p in tool_data.get("parameters", []):
                    p_name = p.get('name') if isinstance(p, dict) else getattr(p, 'name', None)
                    if p_name == k:
                        p_meta = p.get('meta', {}) if isinstance(p, dict) else getattr(p, 'meta', {})
                        g_type = p_meta.get('gql_type') if p_meta else None
                        break
            
            if not g_type:
                # Letzter Fallback: Typ aus dem Python-Wert ableiten
                if isinstance(v, bool):   g_type = "Boolean!"
                elif isinstance(v, int):  g_type = "Int!"
                elif isinstance(v, float): g_type = "Float!"
                elif isinstance(v, list): g_type = "[String]!"  # Besserer Default für Arrays
                else:                     g_type = "String!"
            
            var_defs.append(f"${var_name}: {g_type}")
            var_values[var_name] = v
            arg_calls.append(f"{k}: ${var_name}")

        arg_str = f"({', '.join(arg_calls)})" if arg_calls else ""
        var_def_str = f"({', '.join(var_defs)})" if var_defs else ""
        
        selection_set = self._build_selection_set(select)
        query = f"{operation_type} ElemmQuery{var_def_str} {{ {field_name}{arg_str} {selection_set} }}"
        
        headers = {"User-Agent": self.vault.user_agent, "Content-Type": "application/json"}
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
                try: res_json = resp.json()
                except: pass

                if "errors" in res_json or resp.status_code != 200:
                    debug_echo = {
                        "url": base_url, 
                        "query": query, 
                        "variables": var_values,
                        "available_props": list(tool_data.get("inputSchema", {}).get("properties", {}).keys()),
                        "prop_meta_for_ids": tool_data.get("inputSchema", {}).get("properties", {}).get("ids", {}),
                        "tool_parameters_count": len(tool_data.get("parameters", []))
                    }
                    errors = res_json.get("errors", [])
                    error_msg = errors[0].get("message", "") if errors else resp.text
                    repair = SmartRepairEngine.handle_remote_error(resp.status_code, error_msg)
                    
                    status_map = {401: "AUTHENTICATION_FAILED", 403: "ACCESS_DENIED", 429: "RATE_LIMIT_EXCEEDED", 500: "SERVER_ERROR"}
                    protocol_error = status_map.get(resp.status_code, "GRAPHQL_ERROR")
                    remedy = repair.remedy
                    
                    if "must have a selection of subfields" in error_msg:
                        field_match = re.search(r'Field "(.*?)"', error_msg)
                        target = field_match.group(1) if field_match else "the field"
                        remedy = f"Field '{target}' is an object/interface. You MUST specify sub-fields in '_select' using dot-notation (e.g. '{target}.id' or '{target}.name')."
                        protocol_error = "NESTING_REQUIRED"
                    elif 'Cannot query field "id"' in error_msg:
                        type_match = re.search(r'on type "(.*?)"', error_msg)
                        t_name = type_match.group(1) if type_match else "this type"
                        remedy = f"Type '{t_name}' does not have an 'id' field. You MUST specify valid fields in '_select' (e.g. '_select': 'code,name')."
                        protocol_error = "SELECTION_REQUIRED"
                    elif "Variable" in error_msg and "expecting type" in error_msg:
                        remedy = f"Type mismatch in variables. Expected GQL type not found or inferred incorrectly. Tool has {len(tool_data.get('parameters', []))} params defined."
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
                
                data = res_json.get("data", {}).get(field_name, res_json.get("data"))
                data, was_truncated, total = ResponseSquisher.squish(data, select, None, limit, offset)
                
                if was_truncated:
                    res_obj = {
                        "status": "success",
                        "data": data,
                        "_HYGIENE_NOTICE": f"Output truncated for context hygiene. Showing {len(data)} of {total} items.",
                        "remedy": f"The result is large. Use '_offset={offset + len(data) if offset else len(data)}' to fetch the next page of results."
                    }
                    return json.dumps(res_obj, indent=2)

                return json.dumps(data, indent=2)
        except Exception as e:
            return f"Error executing GraphQL call: {str(e)}"

    def _build_selection_set(self, select: str) -> str:
        from elemm_gateway.services.hygiene import ResponseSquisher
        fields = ResponseSquisher.parse_gql_selection(select)
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
        
        select = arguments.pop("_select", None)
        filter_str = arguments.pop("_filter", None)
        limit = arguments.pop("_limit", None)
        offset = arguments.pop("_offset", None)
        
        if limit: limit = int(limit)
        if offset: offset = int(offset)

        required_fields = tool_data.get("inputSchema", {}).get("required", [])
        # ... (rest of validation logic) ...
        host_key = urlparse(base_url).netloc
        vault_provided = self.vault.get_auth_param_names(host_key)
        
        missing = [f for f in required_fields if f not in arguments and f not in vault_provided]
        if missing:
            schema = tool_data.get("inputSchema", {}).get("properties", {})
            repair = SmartRepairEngine.handle_invalid_params(tool_data.get("name"), missing, schema)
            return json.dumps({
                "status": "error",
                "_PROTOCOL_ERROR": "VALIDATION_FAILED",
                "message": repair.message,
                "remedy": f"The tool '{tool_data.get('name')}' requires these fields: {required_fields}. Check technical signatures with 'inspect_landmark'.",
                "example": f"call_action(action='{tool_data.get('name')}', parameters={ {p: 'VALUE' for p in missing} })"
            }, indent=2)

        full_url = f"{base_url}{path}"
        params = {}
        headers = {"User-Agent": self.vault.user_agent}
        json_body = None

        for param in tool_data.get("parameters", []):
            p_name = param.get('name') if isinstance(param, dict) else getattr(param, 'name', None)
            # BUGFIX: getattr auf Dicts liefert immer den Default ('query'), weil Dicts keine
            # .location-Attribute haben. Deshalb isinstance-Check priorisieren.
            p_in = param.get('location', 'query') if isinstance(param, dict) else getattr(param, 'location', 'query')
            
            if not p_name:
                continue
                
            if p_name in arguments:
                val = arguments[p_name]
                if p_in == "path":
                    # Path-Parameter: in die URL interpolieren UND aus arguments entfernen,
                    # damit er nicht zusätzlich als Query-Parameter landet
                    full_url = full_url.replace(f"{{{p_name}}}", str(val))
                elif p_in == "query":
                    params[p_name] = val
                elif p_in == "header":
                    headers[p_name] = val
                elif p_in == "body":
                    if json_body is None: json_body = {}
                    if isinstance(json_body, dict):
                        json_body[p_name] = val
                    else:
                        json_body = val # Direct payload if not a dict

        self.vault.apply_auth(host_key, params, headers)

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.request(method, full_url, params=params, headers=headers, json=json_body, follow_redirects=True, timeout=30.0)
                
                if resp.status_code != 200:
                    debug_echo = {"method": method, "url": str(resp.url), "constructed_url": full_url, "sent_params": params}
                    error_data = {}
                    try: error_data = resp.json()
                    except: pass
                    error_msg = error_data.get("error", {}).get("message") or error_data.get("message") or resp.text
                    
                    status_map = {400: "BAD_REQUEST", 401: "AUTHENTICATION_FAILED", 403: "ACCESS_DENIED", 404: "NOT_FOUND", 422: "VALIDATION_FAILED", 429: "RATE_LIMIT_EXCEEDED", 500: "SERVER_ERROR"}
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
                data, was_truncated, total = ResponseSquisher.squish(data, select, filter_str, limit, offset)
                
                if was_truncated:
                    # Inject procedural remedy for pagination
                    res_obj = {
                        "status": "success",
                        "data": data,
                        "_HYGIENE_NOTICE": f"Output truncated for context hygiene. Showing {len(data)} of {total} items.",
                        "remedy": f"The result is large. Use '_offset={offset + len(data) if offset else len(data)}' to fetch the next page of results."
                    }
                    return json.dumps(res_obj, indent=2)

                if not data or (isinstance(data, list) and len(data) == 0):
                    return json.dumps({
                        "status": "success",
                        "data": data,
                        "_INFO": "The call was successful but returned no results. Broaden your search/filter if this was unexpected."
                    }, indent=2)
                    
                return json.dumps(data, indent=2)
        except Exception as e:
            return json.dumps({"status": "error", "message": f"Execution failed: {str(e)}"}, indent=2)


class MCPExecutor:
    """Handles execution of tools on external MCP servers."""
    def __init__(self, mcp_bridge: Any):
        self.mcp_bridge = mcp_bridge

    async def execute(self, tool_data: Dict[str, Any], arguments: Dict[str, Any]) -> str:
        meta = tool_data.get("meta", {})
        server_id = meta.get("server_id")
        tool_name = meta.get("tool_name")
        
        if not server_id or not tool_name:
            return json.dumps({
                "status": "error",
                "_PROTOCOL_ERROR": "INVALID_LANDMARK",
                "message": "Landmark is missing server_id or tool_name meta information."
            }, indent=2)

        # Extract hygiene params
        select = arguments.pop("_select", None)
        filter_str = arguments.pop("_filter", None)
        limit = arguments.pop("_limit", None)
        offset = arguments.pop("_offset", None)
        
        if limit: limit = int(limit)
        if offset: offset = int(offset)

        try:
            raw_res = await self.mcp_bridge.call_tool(server_id, tool_name, arguments)
            
            # Try parsing as JSON to apply response hygiene
            try:
                data = json.loads(raw_res)
            except:
                data = raw_res
                
            # Check if parsed JSON represents an API error response (e.g. from Notion/OpenAI/etc.)
            is_json_error = False
            if isinstance(data, dict):
                status_val = data.get("status")
                if isinstance(status_val, int) and status_val >= 400:
                    is_json_error = True
                elif isinstance(status_val, str) and status_val.isdigit() and int(status_val) >= 400:
                    is_json_error = True
                elif data.get("object") == "error":
                    is_json_error = True
                elif "error" in data and isinstance(data["error"], (str, dict)):
                    is_json_error = True
                    
            if is_json_error:
                raise RuntimeError(raw_res)
                
            if isinstance(data, (dict, list)):
                data, was_truncated, total = ResponseSquisher.squish(data, select, filter_str, limit, offset)
                if was_truncated:
                    res_obj = {
                        "status": "success",
                        "data": data,
                        "_HYGIENE_NOTICE": f"Output truncated for context hygiene. Showing {len(data)} of {total} items.",
                        "remedy": f"The result is large. Use '_offset={offset + len(data) if offset else len(data)}' to fetch the next page of results."
                    }
                    return json.dumps(res_obj, indent=2)
                return json.dumps(data, indent=2)
                
            return raw_res
            
        except Exception as e:
            error_msg = str(e)
            
            # Determine remedy from the raw error message
            repair = SmartRepairEngine.handle_mcp_error(error_msg, tool_data)
            remedy = tool_data.get("remedy") or repair.remedy
            
            # If the raw error is already valid JSON, we just inject the remedy to avoid rewriting it
            try:
                err_data = json.loads(error_msg)
                if isinstance(err_data, dict):
                    if remedy:
                        err_data["remedy"] = remedy
                    if "status" not in err_data:
                        err_data["status"] = "error"
                    return json.dumps(err_data, indent=2)
            except:
                pass
                
            # Determine protocol error type
            protocol_error = "EXECUTION_FAILED"
            if "rate limit" in error_msg.lower():
                protocol_error = "RATE_LIMIT_EXCEEDED"
            elif "validation" in error_msg.lower() or "invalid parameter" in error_msg.lower():
                protocol_error = "VALIDATION_FAILED"
                
            res_obj = {
                "status": "error",
                "_PROTOCOL_ERROR": protocol_error,
                "message": error_msg
            }
            if remedy:
                res_obj["remedy"] = remedy
                
            return json.dumps(res_obj, indent=2)
