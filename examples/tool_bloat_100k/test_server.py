import pytest
import httpx
import asyncio
import json
from examples.tool_bloat_100k.server import app

@pytest.mark.asyncio
async def test_bloat_server():
    # We use ASGI transport for standard FastAPI testing, completely avoiding port 8010 and network
    url = "http://testserver"
    
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=url) as client:
        print("--- Testing Manifest ---")
        resp = await client.get("/.well-known/elemm-manifest.md")
        assert resp.status_code == 200
        print(f"Status: {resp.status_code}")
        
        print("\n--- Testing Landmarks (Root: Regions) ---")
        resp = await client.get("/elemm/landmarks")
        assert resp.status_code == 200
        landmarks = resp.json()
        print(f"Root Landmarks Count: {len(landmarks)}")
        print(f"Regions: {[l['id'] for l in landmarks]}")
        
        # Sector_777 ist in der 8. Region (Index 7), da 777 // 100 = 7
        # Regionen sind: Zentrum, Nord, Sued, Ost, West, Nordost, Nordwest, Suedost, Suedwest, Aussenbezirk
        # Index 7 ist 'Suedost'
        target_region = "Suedost"
        target_district = f"{target_region}:Sector_777"
        target_action = f"{target_district}:security:active_alarms"

        print(f"\n--- Testing Inspection (Region: {target_region}) ---")
        resp = await client.get("/.well-known/elemm-manifest.md", params={"landmark_id": target_region})
        assert resp.status_code == 200
        districts = resp.text
        print(f"Status: {resp.status_code}")
        print(f"Contains Sector_777: {target_district in districts}")

        print(f"\n--- Testing Inspection (District: {target_district}) ---")
        resp = await client.get("/.well-known/elemm-manifest.md", params={"landmark_id": target_district})
        assert resp.status_code == 200
        print(f"Status: {resp.status_code}")
        
        print(f"\n--- Testing Execution (The Needle: {target_action}) ---")
        payload = {
            "action": target_action,
            "parameters": {"reason": "Testing the nested needle"}
        }
        resp = await client.post("/.well-known/elemm/execute", json=payload)
        assert resp.status_code == 200
        print(f"Status: {resp.status_code}")
        print(json.dumps(resp.json(), indent=2))

if __name__ == "__main__":
    try:
        asyncio.run(test_bloat_server())
    except Exception as e:
        print(f"Error running in-memory test: {e}")
