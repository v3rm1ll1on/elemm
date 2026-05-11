import asyncio
import json
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from elemm_gateway.server import ElemmGateway
import pytest
import logging

logging.basicConfig(level=logging.INFO)

@pytest.mark.asyncio
async def test_apod_connection():
    gateway = ElemmGateway()
    url = "https://api.apis.guru/v2/specs/nasa.gov/apod/1.0.0/openapi.json"
    
    print(f"Testing connection to {url}...")
    result = await gateway._connect(url)
    
    print("\nConnection Result:")
    for content in result:
        print(content.text)
    
    if gateway.active_site_url:
        print("\nSuccessfully connected!")
        site_data = gateway.connected_sites[url]
        print(f"Discovered {len(site_data['tools'])} tools.")
        
        # Check a few tools
        print("\nSample Tools:")
        for tool in site_data['tools'][:5]:
            print(f"- {tool['name']}: {tool['description']}")
            
        # Verify execution logic (without actually calling Google, just check the metadata)
        tool = site_data['tools'][0]
        tool_name = tool['name']
        print(f"\nChecking metadata for tool: {tool_name}")
        print(f"Description: {tool['description']}")
        print(f"Input Schema: {json.dumps(tool['inputSchema'], indent=2)}")
        
        tool_meta = tool["meta"]
        print(f"Path: {tool_meta['path']}")
        print(f"Method: {tool_meta['method']}")
        print(f"Base URL: {tool_meta['base_url']}")

if __name__ == "__main__":
    asyncio.run(test_apod_connection())
