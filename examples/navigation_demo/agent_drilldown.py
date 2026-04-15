import httpx
import json

API_URL = "http://localhost:8003"

async def run_agent_simulation(task: str):
    print(f"\n🤖 Agent Task: {task}")
    
    async with httpx.AsyncClient() as client:
        # STEP 1: Discover Entry Points (Root Manifest)
        print("\n[Step 1] Fetching Root Manifest...")
        resp = await client.get(f"{API_URL}/.well-known/llm-landmarks.json")
        manifest = resp.json()
        
        # Simulated LLM Logic: "I need to check stock. Looking for a tool..."
        nav_tool = None
        for action in manifest["actions"]:
            if action.get("opens_group") == "Inventory":
                nav_tool = action
                break
        
        if nav_tool:
            print(f"💡 LLM Decision: 'I don't see stock tools here, but I see a navigation landmark: {nav_tool['id']}'")
            print(f"📡 Calling Navigation: {nav_tool['url']}")
            
            # STEP 2: Drill-Down into the Inventory module
            # In a real environment, the LLM would simply call this URL to get its new context
            resp = await client.get(f"{API_URL}{nav_tool['url']}")
            module_manifest = resp.json()
            
            print(f"\n[Step 2] Module 'Inventory' loaded. Entries found: {[a['id'] for a in module_manifest['actions']]}")
            
            # STEP 3: Find the actual tool
            target_tool = next((a for a in module_manifest["actions"] if a["id"] == "check_stock"), None)
            
            if target_tool:
                print(f"✅ LLM Found Target: {target_tool['id']} - {target_tool['description']}")
                print(f"⚙️ Executing: {target_tool['method']} {target_tool['url']}?item_id=AI-Processor")
                
                # STEP 4: Final Action
                resp = await client.get(f"{API_URL}{target_tool['url']}?item_id=AI-Processor")
                print(f"\n🎯 FINAL RESULT: {resp.json()}")
            else:
                print("❌ Target tool not found in module.")
        else:
            print("❌ No navigation path to Inventory found.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_agent_simulation("Find out how many AI-Processors we have in stock."))
