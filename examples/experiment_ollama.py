import httpx
import json
import asyncio
import sys

# Configuration
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "gemma4:latest"
API_URL_CLASSIC = "http://localhost:8001"
API_URL_ELEMM = "http://localhost:8002"

TASK = "Deploy a new Power Core (ID: R-999, Name: Super-Core) to sector 'AREA-51' with security level 5."

async def ollama_request(messages, tools=None):
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0}
    }
    if tools:
        payload["tools"] = tools
        
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(OLLAMA_URL, json=payload)
        return resp.json()

async def run_experiment(name, system_prompt, get_tools_cb):
    print(f"\n{'='*20} EXPERIMENT: {name} {'='*20}")
    
    # 1. Get tools via MCP-like bridge logic
    tools = await get_tools_cb()
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    
    messages.append({"role": "user", "content": TASK})
    
    # Initial Prompt Token Count (Approximate or via Ollama)
    print(f"[Metrics] Tool count: {len(tools)}")
    
    # Simple Loop (Max 3 turns)
    for i in range(3):
        print(f"\n[Turn {i+1}] Thinking...")
        response = await ollama_request(messages, tools)
        
        # Log Tokens
        prompt_tokens = response.get("prompt_eval_count", 0)
        print(f"[Metrics] Prompt Tokens: {prompt_tokens}")
        
        msg = response["message"]
        messages.append(msg)
        
        if not msg.get("tool_calls"):
            print(f"[Final Answer]: {msg['content']}")
            break
            
        for tool_call in msg["tool_calls"]:
            t_name = tool_call["function"]["name"]
            t_args = tool_call["function"]["arguments"]
            print(f"[Action] Calling tool: {t_name}({t_args})")
            
            # Execute tool (Simulated Bridge)
            api_url = API_URL_ELEMM if name == "elemm" else API_URL_CLASSIC
            async with httpx.AsyncClient() as client:
                if t_name == "deploy_resource" or t_name == "create_resource":
                    # Robust extraction for both flat (elemm) and nested (classic) structures
                    sector = t_args.get("sector")
                    if not sector and isinstance(t_args.get("location"), dict):
                        sector = t_args.get("location").get("sector")
                    elif not sector and isinstance(t_args.get("location"), str):
                        sector = t_args.get("location")
                        
                    res_body = {
                        "id": t_args.get("id", "R-999"),
                        "name": t_args.get("name", "Super-Core"),
                        "type": t_args.get("type", "Power"),
                        "status": "active",
                        "location": {
                            "sector": sector or "S-DEFAULT",
                            "coordinates": "0,0",
                            "security_level": t_args.get("security_level", 1)
                        }
                    }
                    r = await client.post(f"{api_url}/resources", json=res_body)
                elif t_name == "list_types" or t_name == "list_categories":
                    r = await client.get(f"{api_url}/categories")
                else:
                    # Generic lookup
                    r = await client.get(f"{api_url}/resources")
                
                result = r.text
                print(f"[Observation] API Result: {result}")
                messages.append({"role": "tool", "content": result, "name": t_name})

async def get_classic_tools():
    # Full manual list to match elemm (6 tools)
    return [
        {"type": "function", "function": {"name": "query_resources", "description": "List and filter corp resources", "parameters": {"type": "object", "properties": {"type": {"type": "string"}, "status": {"type": "string"}}, "required": []}}},
        {"type": "function", "function": {
            "name": "deploy_resource", 
            "description": "Create a new resource", 
            "parameters": {
                "type": "object", 
                "properties": {
                    "id": {"type": "string"}, "name": {"type": "string"}, "type": {"type": "string"},
                    "sector": {"type": "string"}, "security_level": {"type": "integer"}
                },
                "required": ["id", "name", "type", "sector"]
            }
        }},
        {"type": "function", "function": {"name": "list_types", "description": "List all corp resource categories", "parameters": {"type": "object", "properties": {}}}},
        {"type": "function", "function": {"name": "get_resource_detail", "description": "Get details of a specific resource", "parameters": {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}}},
        {"type": "function", "function": {"name": "nexus_analytics", "description": "Get usage stats for the infrastructure", "parameters": {"type": "object", "properties": {}}}},
        {"type": "function", "function": {"name": "system_health", "description": "Internal technical health check", "parameters": {"type": "object", "properties": {}}}}
    ]

async def get_elemm_tools():
    # Real Bridge call to elemm-API
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{API_URL_ELEMM}/.well-known/llm-landmarks.json")
        actions = resp.json()["actions"]
        tools = []
        for a in actions:
            tools.append({
                "type": "function",
                "function": {
                    "name": a["id"],
                    "description": f"{a['description']}\nRemedy: {a.get('remedy', '')}",
                    "parameters": {"type": "object", "properties": {p["name"]: {"type": "string"} for p in (a.get("parameters", []) + a.get("payload", []))}}
                }
            })
        return tools

async def main():
    # 1. CLASSIC RUN
    classic_prompt = (
        "You are a Nexus-Corp Operator. "
        "IMPORTANT RULES: \n"
        "1. If a sector ID is invalid, you will get a 422 error.\n"
        "2. To fix invalid sectors, you MUST call list_categories to see the fleet types (Wait, the human forgot to say 'list sectors').\n"
        "3. Valid sectors are S-1 to S-10."
    )
    # Start classic API in background... (would need manual start or subprocess)
    print("Please make sure BOTH APIs (8001 and 8002) are running!")
    
    await run_experiment("classic", classic_prompt, get_classic_tools)
    await run_experiment("elemm", "", get_elemm_tools)

if __name__ == "__main__":
    asyncio.run(main())
