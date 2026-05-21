import asyncio
import json
import os
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.session import ClientSession

async def main():
    with open(os.path.expanduser("~/.elemm/vault.json")) as f:
        vault = json.load(f)
    
    token = vault.get("notion", {}).get("value")
    if not token:
        print("No notion token found in vault")
        return

    params = StdioServerParameters(
        command="npx",
        args=["-y", "@notionhq/notion-mcp-server"],
        env={**os.environ, "NOTION_TOKEN": token}
    )

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            print("Session initialized. Fetching tools...")
            
            tools = await session.list_tools()
            for tool in tools.tools:
                print(f"--- {tool.name} ---")
                print(tool.description)
                print()

if __name__ == "__main__":
    asyncio.run(main())
