import asyncio
import httpx
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
import mcp.types as types

API_URL = "http://localhost:8001"
server = Server("nexus-legacy-bridge")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """
    PAIN POINT: Manual replication of nested schemas.
    Look at all this JSON-boilerplate we have to write for the AI to understand the API.
    """
    return [
        types.Tool(
            name="list_resources",
            description="List and filter corp resources.",
            inputSchema={
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "status": {"type": "string", "enum": ["active", "maintenance", "offline"]},
                    "min_security": {"type": "integer", "minimum": 0}
                }
            },
        ),
        types.Tool(
            name="create_resource",
            description="Create a complex resource.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "type": {"type": "string"},
                    "status": {"type": "string", "enum": ["active", "maintenance", "offline"]},
                    "location": {
                        "type": "object",
                        "properties": {
                            "sector": {"type": "string"},
                            "coordinates": {"type": "string"},
                            "security_level": {"type": "integer"}
                        },
                        "required": ["sector", "coordinates"]
                    },
                    "tags": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["id", "name", "type", "status", "location"]
            },
        ),
        types.Tool(
            name="get_resource_detail",
            description="Get details of a specific resource.",
            inputSchema={
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"]
            }
        ),
        types.Tool(
            name="get_analytics",
            description="Get usage stats for the infrastructure.",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="list_categories",
            description="List all corp resource categories.",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="update_resource_status",
            description="Update the status of a resource.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "status": {"type": "string", "enum": ["active", "maintenance", "offline"]}
                },
                "required": ["id", "status"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    """
    PAIN POINT: Manual routing for every single action.
    """
    async with httpx.AsyncClient() as client:
        if name == "list_resources":
            resp = await client.get(f"{API_URL}/resources", params=arguments)
            return [types.TextContent(type="text", text=str(resp.json()))]
        elif name == "get_resource_detail":
            resp = await client.get(f"{API_URL}/resources/{arguments.get('id')}")
            return [types.TextContent(type="text", text=str(resp.json()))]
        elif name == "create_resource":
            resp = await client.post(f"{API_URL}/resources", json=arguments)
            return [types.TextContent(type="text", text=str(resp.json()))]
        elif name == "get_analytics":
            resp = await client.get(f"{API_URL}/analytics/usage")
            return [types.TextContent(type="text", text=str(resp.json()))]
        elif name == "list_categories":
            resp = await client.get(f"{API_URL}/categories")
            return [types.TextContent(type="text", text=str(resp.json()))]
        elif name == "update_resource_status":
            resp = await client.patch(f"{API_URL}/resources/{arguments.get('id')}/status", params={"status": arguments.get("status")})
            return [types.TextContent(type="text", text=str(resp.json()))]
        else:
            raise ValueError(f"Unknown tool: {name}")

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, InitializationOptions(
            server_name="nexus-legacy-bridge",
            server_version="0.1.0",
            capabilities=server.get_capabilities(
                notification_options=NotificationOptions(),
                experimental_capabilities={}
            )
        ))

if __name__ == "__main__":
    asyncio.run(main())
