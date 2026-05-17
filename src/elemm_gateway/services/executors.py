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
            return json.dumps({
                "status": "error",
                "_PROTOCOL_ERROR": "VALIDATION_FAILED",
                "message": f"Local Validation Failed: Missing required parameters {missing}",
                "remedy": f"The tool '{tool_data.get('name')}' requires these fields: {required_fields}. Check technical signatures with 'elemm:inspect_landmark'.",
            }, indent=2)

        full_url = f"{base_url}{path}"
        params = {}
        headers = {"User-Agent": "Elemm-Gateway/1.1"}
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
