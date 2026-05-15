import pytest
import httpx
import asyncio
import json

@pytest.mark.asyncio
async def test_bloat_server():
    url = "http://localhost:8010"
    
    async with httpx.AsyncClient() as client:
        print("--- Testing Manifest ---")
        resp = await client.get(f"{url}/.well-known/elemm-manifest.md")
        print(f"Status: {resp.status_code}")
        
        print("\n--- Testing Landmarks (Root: Regions) ---")
        resp = await client.get(f"{url}/elemm/landmarks")
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
        resp = await client.get(f"{url}/.well-known/elemm-manifest.md", params={"landmark_id": target_region})
        districts = resp.text
        print(f"Status: {resp.status_code}")
        print(f"Contains Sector_777: {target_district in districts}")

        print(f"\n--- Testing Inspection (District: {target_district}) ---")
        resp = await client.get(f"{url}/.well-known/elemm-manifest.md", params={"landmark_id": target_district})
        print(f"Status: {resp.status_code}")
        
        print(f"\n--- Testing Execution (The Needle: {target_action}) ---")
        payload = {
            "action": target_action,
            "parameters": {"reason": "Testing the nested needle"}
        }
        resp = await client.post(f"{url}/.well-known/elemm/execute", json=payload)
        print(f"Status: {resp.status_code}")
        print(json.dumps(resp.json(), indent=2))

if __name__ == "__main__":
    try:
        asyncio.run(test_bloat_server())
    except Exception as e:
        print(f"Error: {e}. Is the server running on port 8010?")
