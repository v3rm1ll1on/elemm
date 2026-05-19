import asyncio
import sys
from mcp import ClientSession
from mcp.client.sse import sse_client

async def main():
    print("Attempting to connect to SSE server at http://localhost:8000/sse...")
    try:
        async with sse_client("http://localhost:8000/sse") as (read, write):
            print("Established SSE connection! Initializing session...")
            async with ClientSession(read, write) as session:
                await session.initialize()
                print("Successfully initialized MCP session!")
                tools = await session.list_tools()
                print("\nReceived Tools:")
                for tool in tools.tools:
                    print(f" - {tool.name}: {tool.description}")
    except Exception as e:
        print(f"Error during SSE connection: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
