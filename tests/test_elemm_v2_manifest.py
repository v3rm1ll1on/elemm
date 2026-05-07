import sys
import os
import asyncio
from typing import List

# PYTHONPATH fix
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from elemm_v2.core.manager import AIProtocolManager
from elemm_v2.core.models import Landmark

async def test_manifest_structure():
    print("--- Testing Elemm v2 Manifest Structure ---")
    manager = AIProtocolManager(instructions="Test Instructions")
    
    # Register some tools in namespaces
    @manager.bind("soc:alerts")
    async def get_alerts():
        return "alerts"
        
    @manager.bind("noc:resolve")
    async def resolve():
        return "resolved"
        
    # Get landmarks
    landmarks = manager.get_landmarks()
    print(f"Total Landmarks registered: {len(landmarks)}")
    for lm in landmarks:
        print(f" - ID: {lm.id}, Desc: {lm.description}")

    # Test Presenter
    print("\n--- Testing Presenter Output ---")
    manifest_md = manager.get_manifest_md()
    print(manifest_md)
    
    # Validate requirements
    assert "soc:alerts" in manifest_md
    assert "noc:resolve" in manifest_md
    print("\n✅ Manifest generation successful!")

if __name__ == "__main__":
    asyncio.run(test_manifest_structure())
