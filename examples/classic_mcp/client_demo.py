"""
CLIENT DEMO: The Classic Way (Hard)
This script demonstrates that without elemm, you have to provide a 
huge SYSTEM PROMPT to the AI to teach it how to handle your API.
"""
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# PAIN POINT: We have to manually define the "Rules of Engagement" here.
# Every token in this prompt costs money and context space!
SYSTEM_PROMPT = """
You are a Nexus-Corp Assistant. Here are your manual instructions:
1. When using 'create_resource', you MUST ensure the sector ID is valid.
2. If you get a 422 error on creation, it means the ID is already taken.
3. NEVER set a status to OFFLINE unless you are in a maintenance window.
4. Only use 'list_resources' with security_level >= 5 for sensitive sectors.
(Imagine 50 more lines like this for a real API...)
"""

async def run_classic_agent():
    server_params = StdioServerParameters(
        command="python3",
        args=["examples/classic_mcp/mcp_server.py"]
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            print("\n[Classic Agent] Starting session with huge System Prompt...")
            print(f"System Prompt Length: {len(SYSTEM_PROMPT)} characters")
            
            # The agent now has to hold all these manual rules in its "head" (context)
            print("\n[Classic Agent] Calling 'list_resources'...")
            # Note: The agent has to REMEMBER to apply the rules from the System Prompt.
            result = await session.call_tool("list_resources", arguments={"min_security": 5})
            print(f"[API Response]: {result.content[0].text}")

if __name__ == "__main__":
    try:
        asyncio.run(run_classic_agent())
    except Exception as e:
        print(f"\nError: {e} (Make sure api.py on port 8001 is running)")
