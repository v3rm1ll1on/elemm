"""
CLIENT DEMO: Using Landmarks via MCP Bridge
This script demonstrates how an AI Agent (or a developer) can 
interact with the elemm bridge programmatically.
"""
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def run_agent():
    # 1. Configuration for the bridge
    server_params = StdioServerParameters(
        command="python3",
        args=["examples/elemm_mcp/mcp_server.py"],
        env={"LANDMARK_URL": "http://localhost:8002"}
    )

    # elemm Advantage: NO SYSTEM PROMPT NEEDED!
    # All instructions (Remedy, Instructions, etc.) are embedded 
    # directly in the Tool definitions discovered from the API.
    # This saves context window and keeps logic where it belongs.
    SYSTEM_PROMPT = "" 

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize connection
            await session.initialize()

            # 2. Discovery: List available tools (Landmarks)
            print("\n[Agent] Discovering tools...")
            tools = await session.list_tools()
            for tool in tools.tools:
                print(f"  - Found Landmark: {tool.name} ({tool.description})")

            # 3. Execution: Call a discovered tool
            print("\n[Agent] Calling 'query_resources'...")
            result = await session.call_tool("query_resources", arguments={"min_security": 2})
            print(f"[API Response]: {result.content[0].text}")

if __name__ == "__main__":
    # Ensure the API (examples/elemm_mcp/api.py) is running on port 8002!
    try:
        asyncio.run(run_agent())
    except Exception as e:
        print(f"\nError: {e}")
        print("Tip: Make sure the API (api.py) is running on port 8002.")
