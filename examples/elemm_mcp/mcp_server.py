import asyncio
import httpx
import os
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
import mcp.types as types

# --- elemm Advantage: This file remains 100% STATIC ---
# No matter how many complex endpoints, Nested Models, or Enums 
# you add to your API, THIS bridge script stays exactly the same.
# It is the ultimate "Write Once, Run Forever" bridge.

API_URL = os.getenv("LANDMARK_URL", "http://localhost:8002")
READ_ONLY = os.getenv("LANDMARK_READ_ONLY", "false").lower() == "true"
server = Server("elemm-dynamic-bridge")

async def get_landmarks():
    async with httpx.AsyncClient() as client:
        # Load the auto-generated manifest from the landmark protocol
        url = f"{API_URL}/.well-known/llm-landmarks.json"
        if READ_ONLY:
            url += "?read_only=true"
        resp = await client.get(url)
        return resp.json()["actions"]

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    actions = await get_landmarks()
    tools = []
    for action in actions:
        props = {}
        required = []
        
        # Merge all technical parameters (Query, Path, Body) into one schema
        # elemm has already handled the complex extraction of nested types!
        params = (action.get("parameters") or []) + (action.get("payload") or [])
        for p in params:
            props[p["name"]] = {
                "type": p.get("type", "string"), 
                "description": p.get("description", ""),
            }
            if p.get("options"):
                props[p["name"]]["enum"] = p["options"]
            if p.get("required"): required.append(p["name"])

        tools.append(types.Tool(
            name=action["id"],
            description=f"{action['description']}\nRemedy: {action.get('remedy', '')}",
            inputSchema={"type": "object", "properties": props, "required": required}
        ))
    return tools

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    actions = await get_landmarks()
    action = next(a for a in actions if a["id"] == name)
    
    async with httpx.AsyncClient() as client:
        url = f"{API_URL}{action['url']}"
        method = action["method"]
        
        # Simple dynamic router
        if method == "GET":
            resp = await client.request(method, url, params=arguments)
        else:
            resp = await client.request(method, url, json=arguments)
            
        return [types.TextContent(type="text", text=str(resp.json()))]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, InitializationOptions(
            server_name="elemm-bridge",
            server_version="0.3.1",
            capabilities=server.get_capabilities(
                notification_options=NotificationOptions(),
                experimental_capabilities={}
            )
        ))

if __name__ == "__main__":
    asyncio.run(main())
