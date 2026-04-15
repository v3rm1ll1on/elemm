import asyncio
import os
import httpx
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
import mcp.server.stdio
import mcp.types as types

# Get the target group from environment, or None for Root
TARGET_GROUP = os.environ.get("ELEMM_GROUP")
API_URL = os.environ.get("LANDMARK_URL", "http://localhost:8003")

server = Server("elemm-navigation-bridge")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List tools for the current context (Group)."""
    url = f"{API_URL}/.well-known/llm-landmarks.json"
    if TARGET_GROUP:
        url += f"?group={TARGET_GROUP}"
    
    print(f"DEBUG: Fetching landmarks from {url}", file=sys.stderr)
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        manifest = resp.json()
    
    tools = []
    for action in manifest.get("actions", []):
        # Build property schema
        props = {}
        required = []
        
        # Merge parameters and payload
        all_params = (action.get("parameters") or []) + (action.get("payload") or [])
        if isinstance(all_params, list):
            for p in all_params:
                props[p["name"]] = {
                    "type": p.get("type", "string"),
                    "description": p.get("description", "")
                }
                if p.get("required"):
                    required.append(p["name"])

        tools.append(types.Tool(
            name=action["id"],
            description=f"{action['description']}\n[Remedy: {action.get('remedy', 'Follow instructions')}]",
            inputSchema={
                "type": "object",
                "properties": props,
                "required": required
            }
        ))
    return tools

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    # In a real bridge, we would forward the call to the API URL
    # For the demo, we just echo it.
    return [types.TextContent(type="text", text=f"Call to {name} with args {arguments} would be executed here.")]

async def main():
    import sys
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="elemm-navigation-bridge",
                server_version="0.4.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
