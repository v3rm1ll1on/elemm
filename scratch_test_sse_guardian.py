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
                
                # 1. Connect to site: http://linux-guardian:8003 (Linux Guardian inside the docker compose network)
                print("\n--> Calling connect_to_site for http://linux-guardian:8003...")
                res_connect = await session.call_tool("connect_to_site", {"url": "http://linux-guardian:8003"})
                print(f"Response: {res_connect.content[0].text if res_connect.content else 'Empty response'}")
                
                # 2. Get the manifest
                print("\n--> Calling get_manifest...")
                res_manifest = await session.call_tool("get_manifest", {})
                print(f"Response: {res_manifest.content[0].text[:400] if res_manifest.content else 'Empty response'}...")
                
                # 3. List the system info
                print("\n--> Calling call_action to run system:get_info...")
                res_info = await session.call_tool("call_action", {
                    "action_name": "system:get_info",
                    "parameters": {}
                })
                print(f"Response from system:get_info: {res_info.content[0].text if res_info.content else 'Empty response'}")
                
    except Exception as e:
        print(f"Error during SSE connection: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
