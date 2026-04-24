import asyncio
import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server
import httpx
from api_classic import app

server = Server("solaris-classic-mcp")

def get_tool_name(route):
    # Convert route path to a tool name (e.g. /soc/alerts -> soc_alerts)
    name = route.path.strip("/").replace("/", "_").replace("{", "").replace("}", "")
    if not name:
        return "root"
    return name

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    tools = []
    for route in app.routes:
        # We only care about actual API routes (not openapi.json etc)
        if hasattr(route, "endpoint") and not route.path.startswith("/openapi") and not route.path.startswith("/docs"):
            name = get_tool_name(route)
            desc = route.endpoint.__doc__ or f"Classic endpoint for {route.path}"
            
            # Simple schema generation for classic mode
            schema = {"type": "object", "properties": {}, "required": []}
            
            # Try to find path parameters
            import re
            path_params = re.findall(r"\{(\w+)\}", route.path)
            for param in path_params:
                schema["properties"][param] = {"type": "string"}
                schema["required"].append(param)
            
            # Note: For classic mode, we keep it simple as a human would likely define it
            # In a real "classic" setup, many tools wouldn't even have complex schemas.
            
            # Special handling for known mission tools to ensure they are at least somewhat usable
            if "quarantine" in name:
                schema["properties"] = {
                    "username": {"type": "string", "description": "Corporate Username"},
                    "token": {"type": "string", "description": "Evidence Token"}
                }
                schema["required"] = ["username", "token"]
            elif "restart" in name:
                schema["properties"] = {"hostname": {"type": "string"}}
                schema["required"] = ["hostname"]
            elif "report" in name:
                schema["properties"] = {"incident_id": {"type": "string"}, "summary": {"type": "string"}}
                schema["required"] = ["incident_id", "summary"]
            elif "resolve" in name or "query" in name or "audit" in name or "link" in name:
                # Add one generic 'param' if we missed it
                if not schema["properties"]:
                    # We look at the first parameter of the function if possible
                    import inspect
                    sig = inspect.signature(route.endpoint)
                    for p_name, p in sig.parameters.items():
                        if p_name != "request":
                            schema["properties"][p_name] = {"type": "string"}
                            schema["required"].append(p_name)
                            break

            tools.append(types.Tool(name=name, description=desc, inputSchema=schema))
            
    return tools

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    # Find the matching route
    target_route = None
    for route in app.routes:
        if get_tool_name(route) == name:
            target_route = route
            break
            
    if not target_route:
        return [types.TextContent(type="text", text=f"Error: Tool {name} not found")]

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        method = list(target_route.methods)[0] if target_route.methods else "GET"
        url = target_route.path
        
        # Fill path params
        params_to_use = (arguments or {}).copy()
        import re
        path_params = re.findall(r"\{(\w+)\}", url)
        for p in path_params:
            if p in params_to_use:
                url = url.replace(f"{{{p}}}", str(params_to_use.pop(p)))
        
        if method in ["POST", "PUT", "PATCH"]:
            resp = await client.request(method, url, json=params_to_use)
        else:
            resp = await client.request(method, url, params=params_to_use)
            
        return [types.TextContent(type="text", text=resp.text)]

async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
