import asyncio
import yaml
from elemm.core.manager import LandmarkManager

# 1. Define a minimal set of landmarks
LANDMARKS_CONFIG = """
landmarks:
  - id: "calc"
    description: "Simple arithmetic operations."
    tools:
      - id: "add"
        description: "Add two numbers."
        parameters:
          - name: "a"
            type: "number"
            required: true
          - name: "b"
            type: "number"
            required: true
        returns: "{ result: number }"
"""

async def main():
    # 2. Initialize the Manager
    config = yaml.safe_load(LANDMARKS_CONFIG)
    manager = LandmarkManager(config)
    
    # 3. Register a simple tool handler
    @manager.register_tool("calc:add")
    async def add_handler(a, b):
        return {"result": a + b}
    
    # 4. Execute a sequence with piping
    sequence = [
        {
            "action": "calc:add",
            "alias": "step1",
            "parameters": {"a": 10, "b": 20}
        },
        {
            "action": "calc:add",
            "parameters": {"a": "$step1.result", "b": 5}
        }
    ]
    
    print("🚀 Executing sequence...")
    results = await manager.execute_sequence(sequence)
    
    for i, res in enumerate(results):
        print(f"Step {i}: {res}")

if __name__ == "__main__":
    asyncio.run(main())
