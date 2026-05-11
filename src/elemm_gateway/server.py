import os
import json
import logging
import asyncio
import re
import httpx
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions

import yaml
from elemm_gateway.openapi_bridge import OpenAPIBridge
from elemm_gateway.graphql_bridge import GraphQLBridge
from elemm_gateway.components import (
    VaultManager, 
    OpenAPIExecutor, 
    GraphQLExecutor,
    ResponseSquisher, 
    SequenceEngine
)

logger = logging.getLogger("elemm-gateway")

class ElemmGateway:
    """
    Elemm Gateway v2: A component-based gateway for autonomous tool discovery
    and hygienic execution across Native, OpenAPI, and GraphQL interfaces.
    """
    
    SECTION_PATTERN = re.compile(r"### PROTOCOL RULES\n(.*?)\n###", re.DOTALL)
    JSON_BLOCK_PATTERN = re.compile(r"```json-elemm\n(.*?)\n```", re.DOTALL)

    def __init__(self, server_name: str = "elemm-gateway"):
        # Connected sites storage: {url: {manifest, tools, directive, type}}
        self.connected_sites: Dict[str, Dict[str, Any]] = {}
        self.active_site_url: Optional[str] = None
        self.manifest_loaded = False

        # Modular Components
        self.vault_manager = VaultManager(os.path.expanduser("~/.elemm/vault.json"))
        self.openapi_executor = OpenAPIExecutor(self.vault_manager)
        self.graphql_executor = GraphQLExecutor(self.vault_manager)
        self.sequence_engine = SequenceEngine(self)

        self.server = Server(server_name)
        self._setup_handlers()

    def _setup_handlers(self):
        @self.server.list_tools()
        async def handle_list_tools() -> List[types.Tool]:
            """Lists core gateway tools and tools from the active remote site."""
            core_tools = [
                types.Tool(
                    name="connect_to_site",
                    description="Connect to an Elemm-compliant website, OpenAPI, or GraphQL API via its URL.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "The URL to connect to (e.g., https://api.example.com/openapi.json)"}
                        },
                        "required": ["url"]
                    }
                ),
                types.Tool(
                    name="get_manifest",
                    description="CRITICAL: Get system instructions and command topology from the active site.",
                    inputSchema={"type": "object", "properties": {}}
                ),
                types.Tool(
                    name="call_action",
                    description="Execute a single action on the remote site. Supports hygiene (_select, _filter, _limit).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "action": {"type": "string", "description": "The Action ID to execute."},
                            "parameters": {"type": "object", "description": "Parameters for the action."}
                        },
                        "required": ["action"]
                    }
                ),
                types.Tool(
                    name="execute_sequence",
                    description="NATIVE PIPELINE: Batch tools in one turn. Every step creates an automatic alias ($step0, $step1...). Access nested data via $alias.path (e.g., $weather.current.temp).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "actions": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "action": {"type": "string"},
                                        "alias": {"type": "string"},
                                        "parameters": {"type": "object"}
                                    },
                                    "required": ["action"]
                                }
                            },
                            "steps": {
                                "type": "array",
                                "description": "Alias for 'actions'.",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "action": {"type": "string"},
                                        "alias": {"type": "string"},
                                        "parameters": {"type": "object"}
                                    },
                                    "required": ["action"]
                                }
                            }
                        }
                    }
                )
            ]

            if self.active_site_url and self.active_site_url in self.connected_sites:
                site_tools = self.connected_sites[self.active_site_url].get("tools", [])
                # Convert site tools to MCP format if they aren't already
                mcp_site_tools = []
                for t in site_tools:
                    mcp_site_tools.append(types.Tool(
                        name=t["name"],
                        description=t["description"],
                        inputSchema=t["inputSchema"]
                    ))
                return core_tools + mcp_site_tools
            
            return core_tools

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict | None) -> List[types.TextContent]:
            """Main dispatcher for tool calls."""
            arguments = arguments or {}
            logger.info(f"Gateway: Dispatching tool '{name}'")

            if name == "connect_to_site":
                return await self._connect(arguments.get("url", ""))
            
            if name == "execute_sequence":
                return await self.sequence_engine.execute(**arguments)

            # Core Tool Proxying
            if name in ["get_manifest", "get_landmarks", "inspect_landmark", "list_aliases"]:
                return await self._proxy_core_tool(name, arguments)

            # Action Execution
            if name == "call_action":
                res = await self._execute_single(arguments.get("action", ""), arguments.get("parameters", {}))
                return self._format_result(res)

            # Direct Call (for site-specific tools)
            res = await self._execute_single(name, arguments)
            return self._format_result(res)

    async def _handle_execute_sequence(self, actions: List[Dict]) -> List[types.TextContent]:
        """Backward compatibility shim for tests."""
        return await self.sequence_engine.execute(actions)

    async def _handle_call_tool(self, name: str, arguments: dict) -> List[types.TextContent]:
        """Backward compatibility shim for tests."""
        if name == "execute_sequence":
            return await self._handle_execute_sequence(arguments.get("actions", []))
        
        # Check core tools
        if name in ["connect_to_site", "get_manifest", "get_landmarks", "inspect_landmark", "list_aliases"]:
            if name == "connect_to_site":
                return await self._connect(arguments.get("url", ""))
            if name == "list_aliases":
                aliases = self.sequence_engine.list_aliases()
                res = "### MEMORY BANK (Current Aliases)\n"
                if not aliases:
                    res += "- No findings stored yet."
                else:
                    for a, v in sorted(aliases.items()):
                        res += f"- **${a}**: {v}\n"
                return [types.TextContent(type="text", text=res)]
            return await self._proxy_core_tool(name, arguments)
        if name == "call_action":
            res = await self._execute_single(arguments.get("action", ""), arguments.get("parameters", {}))
            return self._format_result(res)
            
        res = await self._execute_single(name, arguments)
        return self._format_result(res)

    def _format_result(self, text_val: Any) -> List[types.TextContent]:
        warning = "\n\n(HINT: Use 'execute_sequence' for better performance and token efficiency!)"
        return [types.TextContent(type="text", text=str(text_val) + warning)]

    async def _proxy_core_tool(self, name: str, arguments: Dict) -> List[types.TextContent]:
        """Proxies core tools to the remote site or serves them from cache for OpenAPI/GraphQL."""
        url = self.active_site_url
        if not url:
            return [types.TextContent(type="text", text="Error: Not connected to any site.")]

        site_data = self.connected_sites.get(url)
        if not site_data:
            # Try fuzzy match if url has/lacks trailing slash
            alt_url = url.rstrip("/") if url.endswith("/") else f"{url}/"
            site_data = self.connected_sites.get(alt_url)
        
        if site_data:
            logger.info(f"Gateway: Serving '{name}' locally from cache for {url}")
            if name == "get_manifest":
                return [types.TextContent(type="text", text=site_data["manifest"])]
            if name == "get_landmarks":
                if site_data.get("type") == "native":
                    # For native sites, extract topology from the manifest text
                    manifest = site_data.get("manifest", "")
                    landmarks = {}
                    # Simple regex to find "- **`id`**: ..."
                    matches = re.findall(r"- \*\*`(.*?)`\*\*: (.*?)\n", manifest)
                    for lid, desc in matches:
                        if lid == "elemm": continue
                        landmarks[lid] = desc
                    
                    res = "### LANDMARK TOPOLOGY\n"
                    for lid, desc in sorted(landmarks.items()):
                        res += f"- **{lid}**: {desc}\n"
                    return [types.TextContent(type="text", text=res)]
                
                # Fallback for OpenAPI/GraphQL
                tools = site_data.get("tools", [])
                landmarks = {}
                for t in tools:
                    lm = t["name"].split(":")[0] if ":" in t["name"] else t["name"].split("_", 1)[0]
                    landmarks[lm] = landmarks.get(lm, 0) + 1
                
                res = "### LANDMARK TOPOLOGY\n"
                for lm, count in sorted(landmarks.items()):
                    res += f"- **{lm}**: ({count} tools)\n"
                return [types.TextContent(type="text", text=res)]

            if name == "inspect_landmark":
                lm_id = arguments.get("landmark_id")
                ids = [lm_id] if isinstance(lm_id, str) else lm_id
                
                if site_data.get("type") == "native":
                    # Lazy Load from remote site
                    signatures = []
                    async with httpx.AsyncClient() as client:
                        for tid in ids:
                            inspect_url = f"{self.active_site_url}/.well-known/elemm-manifest.md"
                            resp = await client.get(inspect_url, params={"landmark_id": tid, "technical": "true"}, follow_redirects=True)
                            if resp.status_code == 200:
                                content = resp.text
                                # CLEANUP: Strip technical JSON block from inspection too
                                if "---" in content:
                                    content = content.split("---")[0].strip()
                                signatures.append(content)
                    
                    final_md = "\n\n".join(signatures)
                    return [types.TextContent(type="text", text=final_md)]

                # Fallback for OpenAPI/GraphQL (already parsed)
                signatures = []
                for tid in ids:
                    # Match exact tool ID or all tools in a landmark namespace
                    relevant_tools = [t for t in site_data["tools"] if t["name"] == tid or t["name"].startswith(f"{tid}:") or t["name"].startswith(f"{tid}_")]
                    
                    for t in relevant_tools:
                        props = t['inputSchema'].get('properties', {})
                        required = t['inputSchema'].get('required', [])
                        
                        sig = f"/**\n * Tool: {t['name']}\n * Description: {t['description']}\n"
                        for p_name, p_schema in props.items():
                            p_type = p_schema.get('type', 'any')
                            p_desc = p_schema.get('description', '')
                            req_mark = "[REQUIRED]" if p_name in required else "[OPTIONAL]"
                            sig += f" * @param {p_name} ({p_type}) {req_mark} {p_desc}\n"
                        sig += " */\n"
                        
                        # Generate TS-style signature
                        params_list = []
                        for p_name, p_schema in props.items():
                            p_type = p_schema.get('type', 'any')
                            opt = "" if p_name in required else "?"
                            params_list.append(f"{p_name}{opt}: {p_type}")
                        
                        sig += f"function call_action(action: '{t['name']}', parameters: {{ {', '.join(params_list)} }}): any;\n"
                        signatures.append(sig)
                
                if not signatures:
                    content = f"No tools found for landmark/id '{ids}'. Use 'elemm:get_landmarks' to see valid names."
                else:
                    content = "### TECHNICAL SIGNATURES\n```typescript\n" + "\n\n".join(signatures) + "\n```"
                    content += "\n\n(HINT: Combine multiple calls into one 'execute_sequence' for maximum token efficiency!)"
                
                return [types.TextContent(type="text", text=self._inject_global_landmark(content))]
            
            if name == "list_aliases":
                aliases = self.sequence_engine.list_aliases()
                res = "### MEMORY BANK (Current Aliases)\n"
                if not aliases:
                    res += "- No findings stored yet."
                else:
                    for a, v in sorted(aliases.items()):
                        res += f"- **${a}**: {v}\n"
                return [types.TextContent(type="text", text=res)]
            
            if name == "execute_sequence":
                return await self.sequence_engine.execute(arguments.get("actions", []))

        return [types.TextContent(type="text", text=f"Error: Core tool '{name}' not supported by gateway.")]

    async def _execute_single(self, tool_name: str, arguments: Dict) -> str:
        """UNIVERSAL PROXY: Sends the call to the remote site's execution endpoint or directly via HTTP for OpenAPI/GraphQL."""
        if not self.active_site_url and tool_name not in ["connect_to_site"] and not tool_name.startswith("elemm:"):
            return "Error: Gateway not connected to a remote site."

        if tool_name == "execute_sequence":
            res = await self.sequence_engine.execute(arguments.get("actions", []))
            return res[0].text if res else "No result"

        # Handle Internal Meta Tools (Token Efficiency Optimization)
        if tool_name == "connect_to_site":
            res = await self._connect(arguments.get("url", ""))
            return res[0].text if res else "Connected"

        if tool_name.startswith("elemm:"):
            internal_name = tool_name.split(":", 1)[1]
            # Use proxy logic but return stringified result
            res = await self._proxy_core_tool(internal_name, arguments)
            return res[0].text if res else "No result"

        site_data = self.connected_sites.get(self.active_site_url)
        if site_data.get("type") in ["openapi", "graphql"]:
            return await self._execute_openapi(tool_name, arguments)

        try:
            async with httpx.AsyncClient() as client:
                # Use v2 execution endpoint
                exec_url = f"{self.active_site_url}/.well-known/elemm/execute"
                payload = {"action": tool_name, "parameters": arguments}
                logger.info(f"Gateway: Executing native call to {exec_url}")
                
                resp = await client.post(exec_url, json=payload, timeout=60.0)
                if resp.status_code != 200:
                    return f"Remote Execution Error: HTTP {resp.status_code}\n{resp.text}"
                return json.dumps(resp.json(), indent=2)
        except Exception as e:
            return f"Gateway Connection Error: {str(e)}"

    async def _execute_openapi(self, name: str, arguments: Dict[str, Any]) -> str:
        """Proxies a tool call to the remote OpenAPI or GraphQL endpoint."""
        from elemm.core.repair import SmartRepairEngine
        
        url = self.active_site_url
        site_data = self.connected_sites.get(url)
        if not site_data:
            return json.dumps({
                "status": "error",
                "message": "Gateway not connected to any site.",
                "remedy": "Use 'connect_to_site' first."
            })
        
        # Find tool meta
        tool_data = next((t for t in site_data["tools"] if t["name"] == name), None)
        if not tool_data:
            # Check if it's a Landmark Namespace (Grouping)
            landmarks = set(t["name"].split("_", 1)[0] for t in site_data["tools"] if "_" in t["name"])
            if name in landmarks:
                repair = SmartRepairEngine.handle_namespace_execution_attempt(name)
                return json.dumps(repair.model_dump(), indent=2)

            # SmartRepair: Find close matches
            available_ids = [t["name"] for t in site_data["tools"]]
            repair = SmartRepairEngine.handle_missing_action(name, available_ids)
            return json.dumps(repair.model_dump(), indent=2)
        
        try:
            if site_data.get("type") == "graphql":
                return await self.graphql_executor.execute(tool_data, arguments)
            else:
                return await self.openapi_executor.execute(tool_data, arguments)
        except Exception as e:
            return json.dumps({
                "status": "error",
                "message": f"Execution failed: {str(e)}",
                "remedy": "Verify technical signatures with 'elemm:inspect_landmark'."
            }, indent=2)

    async def _connect(self, url: str) -> List[types.TextContent]:
        """Fetches the .md manifest and establishes the session."""
        from elemm_gateway.components import ManifestBuilder
        url = url.strip().rstrip("/")
        logger.info(f"Gateway: Connecting to URL: '{url}'")
        try:
            async with httpx.AsyncClient() as client:
                # Reload vault on each connect to avoid restarts
                self.vault_manager.vault = self.vault_manager.load()
                
                # 1. Check for GraphQL (Introspection Probing)
                if "graphql" in url.lower():
                    logger.info(f"Gateway: GraphQL keyword detected in {url}. Probing...")
                    try:
                        resp = await client.post(
                            url,
                            json={"query": GraphQLBridge.INTROSPECTION_QUERY},
                            headers={
                                "Content-Type": "application/json",
                                "User-Agent": "Elemm-Gateway/2.0"
                            },
                            follow_redirects=True,
                            timeout=15.0
                        )
                        if resp.status_code == 200:
                            schema_data = resp.json().get("data")
                            if schema_data:
                                logger.info(f"Gateway: Detected GraphQL API at {url}")
                                parsed = GraphQLBridge.parse_schema(schema_data, url)
                                md_content = OpenAPIBridge.generate_virtual_manifest(parsed)
                                
                                self.connected_sites[url] = {
                                    "manifest": md_content,
                                    "tools": parsed["tools"],
                                    "type": "graphql"
                                }
                                self.active_site_url = url
                                return [types.TextContent(type="text", text=f"Connected to GraphQL API: {url}\n\nManifest generated dynamically via Introspection.")]
                            else:
                                return [types.TextContent(type="text", text=f"GraphQL Probing at {url} returned 200 but no 'data'. Body: {resp.text}")]
                        else:
                            return [types.TextContent(type="text", text=f"GraphQL Probing at {url} failed with HTTP {resp.status_code}. Body: {resp.text}")]
                    except Exception as e:
                        logger.warning(f"Gateway: GraphQL probing failed for {url}: {e}")
                        return [types.TextContent(type="text", text=f"GraphQL Probing Error: {str(e)}")]

                # 2. Check if it's an OpenAPI JSON/YAML URL
                if any(url.endswith(ext) for ext in [".json", ".yaml", ".yml"]) or "/openapi" in url:
                    try:
                        resp = await client.get(url, follow_redirects=True, timeout=10.0)
                        if resp.status_code == 200:
                            # Try JSON first, then YAML
                            try:
                                spec = resp.json()
                            except:
                                spec = yaml.safe_load(resp.text)

                            if isinstance(spec, dict) and ("openapi" in spec or "swagger" in spec):
                                logger.info(f"Gateway: Detected OpenAPI spec at {url}")
                                parsed = OpenAPIBridge.parse_spec(spec, url.rsplit("/", 1)[0])
                                md_content = OpenAPIBridge.generate_virtual_manifest(parsed)
                                
                                self.connected_sites[url] = {
                                    "manifest": md_content,
                                    "tools": parsed["tools"],
                                    "type": "openapi",
                                    "spec": spec
                                }
                                self.active_site_url = url
                                
                                # Check for Auth Requirements
                                auth_warning = ""
                                target_url = parsed.get("base_url", "")
                                host_key = urlparse(target_url).netloc if target_url else urlparse(url).netloc
                                
                                schemes = parsed.get("security_schemes", {})
                                if schemes and host_key not in self.vault_manager.vault:
                                    auth_warning = (
                                        "\n\n> [!WARNING]\n"
                                        f"> **AUTHENTICATION REQUIRED**: This site requires {list(schemes.keys())[0]}.\n"
                                        f"> **REMEDY**: Add an entry for '{host_key}' to your `~/.elemm/vault.json`.\n"
                                        "> **INSTRUCTION**: Please inform the user that an API key is required for this service."
                                    )
                                
                                return [types.TextContent(type="text", text=f"Connected to OpenAPI API: {url}\n\nManifest generated dynamically.{auth_warning}")]
                    except Exception as e:
                        logger.warning(f"Gateway: Failed to probe OpenAPI at {url}: {e}")

                # 3. Standard Elemm Manifest discovery (Lazy Loading Pattern)
                manifest_url = f"{url}/.well-known/elemm-manifest.md"
                try:
                    # Only fetch the summary manifest initially (No technical=true here!)
                    resp = await client.get(manifest_url, follow_redirects=True, timeout=10.0)
                    if resp.status_code == 200:
                        md_content = self._inject_global_landmark(resp.text)
                        
                        # Extract AGENT DIRECTIVE
                        match = self.SECTION_PATTERN.search(md_content)
                        directive = match.group(1).strip() if match else ManifestBuilder.PROTOCOL_RULES
                        
                        # In Lazy Loading, we don't parse tools yet. 
                        # We just store the manifest for topology discovery.
                        self.connected_sites[url] = {
                            "manifest": md_content,
                            "tools": [], # Will be filled on-demand or used via proxy
                            "directive": directive,
                            "type": "native"
                        }
                        self.active_site_url = url
                        self.manifest_loaded = True
                        return [types.TextContent(type="text", text=f"Connected to Elemm site: {url}\n\nManifest (Summary) loaded successfully.")]
                except Exception as e:
                    logger.warning(f"Gateway: Native manifest discovery failed for {url}: {e}")

                return [types.TextContent(type="text", text=f"Failed to find a supported interface at {url}. (Checked GraphQL, OpenAPI, and Native Elemm)")]

        except Exception as e:
            logger.exception("Gateway: Connection fatal error")
            return [types.TextContent(type="text", text=f"Gateway Connection Error: {str(e)}")]

    def _inject_global_landmark(self, manifest: str) -> str:
        """Injects the virtual 'elemm' landmark and updates discovery hints."""
        from elemm_gateway.components import ManifestBuilder
        return ManifestBuilder.inject_globals(manifest)

    def _parse_manifest_to_tools(self, md_content: str) -> List[Dict[str, Any]]:
        """Parses technical tools from the json-elemm block in the manifest."""
        mcp_tools = []
        json_match = self.JSON_BLOCK_PATTERN.search(md_content)
        if json_match:
            try:
                mcp_tools = json.loads(json_match.group(1))
                logger.info(f"Gateway: Discovered {len(mcp_tools)} technical tools via json-elemm.")
            except Exception as e:
                logger.warning(f"Gateway: Failed to parse json-elemm block: {e}")
        return mcp_tools

    async def run(self):
        """Runs the MCP server."""
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="elemm-gateway",
                    server_version="2.0.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    gateway = ElemmGateway("elemm-gateway")
    asyncio.run(gateway.run())
