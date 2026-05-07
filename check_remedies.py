import asyncio
import json
from elemm_v2.core.manager import AIProtocolManager
from elemm_v2.core.exceptions import ActionError

async def test_remedy_injection():
    manager = AIProtocolManager(instructions="Test")
    
    @manager.bind("fail_tool")
    def fail_tool():
        # Wir definieren eine Remedy in der Registry (simuliert YAML)
        raise Exception("VRAM Full")

    # Manuell Remedy setzen (da kein YAML geladen wird)
    manager.landmarks["fail_tool"].remedy = "Try restarting the node."

    print("--- TESTING ERROR RESPONSE ---")
    res = await manager.call_action("fail_tool", {})
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    asyncio.run(test_remedy_injection())
