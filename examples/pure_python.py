import asyncio
import json
from elemm.core.manager import BaseAIProtocolManager
from elemm.core.models import ActionParam
from elemm.mcp.bridge import LandmarkBridge

async def run_pure_python_example():
    # 1. Initialize the Core Protocol Manager (No FastAPI!)
    manager = BaseAIProtocolManager(
        agent_welcome="Pure Python Elemm",
        protocol_instructions="This runs completely without HTTP servers or FastAPI."
    )

    # 2. Register a native Python tool with explicit parameters
    @manager.tool(
        id="analyze_data",
        description="Analyzes a list of numbers and returns their sum and average.",
        parameters=[
            ActionParam(name="numbers", type="array", required=True, description="List of integers to analyze")
        ]
    )
    async def analyze_data(numbers: list[int]):
        print(f"[NATIVE] Executing analyze_data with: {numbers}")
        if not numbers:
            return {"sum": 0, "average": 0}
        return {
            "sum": sum(numbers),
            "average": sum(numbers) / len(numbers)
        }

    # 3. Create the LandmarkBridge (Bridge to MCP)
    bridge = LandmarkBridge(manager=manager)
    
    print("=== 1. Generated MCP Tools ===")
    mcp_tools = bridge.get_full_mcp_definitions()
    for tool in mcp_tools:
        print(f"Tool: {tool['name']}")
        print(f"Schema: {json.dumps(tool['inputSchema'], indent=2)}")
        
    print("\n=== 2. Simulating direct Execution ===")
    # Direct Execution through the core manager!
    # This bypasses the need for an HTTP layer.
    result, status = await manager.call_action("analyze_data", {"numbers": [10, 20, 30, 40]})
    
    print(f"Status Code: {status}")
    print(f"Result: {json.dumps(result, indent=2)}")

if __name__ == "__main__":
    asyncio.run(run_pure_python_example())
