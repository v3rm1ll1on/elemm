import sys
import os
import argparse
import asyncio
import httpx
import json
import time
from typing import Any
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from metrics_collector import BenchmarkMetrics

OLLAMA_URL = "http://192.168.178.76:11434/api/chat"
MODEL = "gemma4:e2b"

def estimate_tokens(obj: Any) -> int:
    """Rough heuristic for token count (characters / 4)."""
    return len(json.dumps(obj)) // 4

async def run_agent(task_prompt: str, server_script: str, is_classic: bool, quiet=False, num_ctx=32768):
    mode_name = "classic" if is_classic else "elemm"
    metrics = BenchmarkMetrics(mode=mode_name, task=task_prompt)
    
    def log(msg):
        if not quiet:
            print(msg)

    args_list = [os.path.join(os.path.dirname(__file__), server_script)]
    if not is_classic:
        args_list.append("--mcp")

    server_params = StdioServerParameters(
        command=sys.executable,
        args=args_list,
        env=os.environ.copy()
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            discovery_res = await session.list_tools()
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.inputSchema
                    }
                } for t in discovery_res.tools
            ]
            log(f"🔍 Discovered {len(tools)} tools: {[t['function']['name'] for t in tools]}")
            
            async with httpx.AsyncClient() as chat_client:
                # v1 Genius: System Persona and Mode-Specific Instructions
                shared_persona = (
                    "You are the Solaris Forensic Auditor. Your style is purely technical, silent, and decisive. "
                    "DO NOT EXPLAIN. Output ONLY valid tool calls to resolve the incident. Results are the only metric of success."
                )

                if is_classic:
                    system_prompt = (
                        f"{shared_persona}\n\n"
                        "### SOLARIS TECHNICAL REFERENCE MANUAL ###\n"
                        "1. NETWORK & INFRA: Internal IP addresses can be resolved to Hostnames via the NOC. Infrastructure logs are stored in IT and indexed by Hostname.\n"
                        "2. PERSONNEL & FINANCE: Employee IDs (EMP-XXXX) are used in HR and Finance. Corporate Usernames (CORP-XX) are resolved in HR. Financial accounts are linked to tokens in Banking.\n"
                        "3. REMEDIATION PROTOCOLS: \n"
                        "   - All quarantine actions REQUIRE a Corporate Username (NOT EMP-ID) and a matching Evidence Token (RT-XXXX) from IT logs.\n"
                        "   - Infrastructure restarts require a verified SRV-XXXX hostname.\n"
                        "   - Final reports must be submitted via the OPS reporter once all mitigation flags are set to SUCCESS in the MISSION_STATE.\n"
                        "4. COMPLIANCE: Adhere strictly to provided technical schemas. Do not attempt to use unresolved IDs for state-changing operations."
                    )
                else:
                    # In ELEMM mode, we trust the Tool Descriptions and the Protocol Handshake.
                    system_prompt = (
                        f"{shared_persona}\n\n"
                        "Use the available tools to investigate and resolve the incident. "
                        "Follow the protocol hints provided in the tool descriptions."
                    )

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": task_prompt}
                ]
                
                for i in range(1, 31):
                    # Calculate FULL context size (Messages + Tools)
                    ctx_size = estimate_tokens(messages) + estimate_tokens(tools)
                    log("\n" + "="*80)
                    log(f" STEP {i} | Model: {MODEL} | Ctx: ~{ctx_size}")
                    log("="*80)
                    
                    start_t = time.time()
                    response = await chat_client.post(OLLAMA_URL, json={
                        "model": MODEL,
                        "messages": messages,
                        "tools": tools,
                        "stream": False,
                        "options": {"num_ctx": num_ctx}
                    }, timeout=120.0)
                    latency = (time.time() - start_t) * 1000
                    
                    if response.status_code != 200:
                        log(f"❌ Ollama Error: {response.text}")
                        break
                        
                    resp_json = response.json()
                    agent_msg = resp_json.get("message", {})
                    content = agent_msg.get("content", "")
                    tool_calls = agent_msg.get("tool_calls", [])
                    
                    # Estimate tokens for this turn
                    tokens_in = ctx_size
                    tokens_out = estimate_tokens(agent_msg)
                    
                    messages.append(agent_msg)
                    metrics.add_step(tokens_in, tokens_out, latency, ctx_size)
                    
                    if content:
                        log(f"🤖 AGENT: {content}")

                    if not tool_calls:
                        if i < 30:
                            log("⚠️ No tool calls. Nudging agent to retry...")
                            messages.append({
                                "role": "user", 
                                "content": "I noticed you didn't call any tools. If you are stuck due to a previous error, analyze the 'remedy' or 'message' field in the last tool result and try a corrected approach."
                            })
                            continue
                        else:
                            log("⚠️ No tool calls. Mission stagnant.")
                            break

                    for tc in tool_calls:
                        name = tc["function"]["name"]
                        args = tc["function"]["arguments"]
                        log(f"🛠️ CALLING: {name}({args})")
                        
                        try:
                            start_tool_t = time.time()
                            result = await session.call_tool(name, args)
                            tool_latency = (time.time() - start_tool_t) * 1000
                            
                            res_text = result.content[0].text if result.content else "No output"
                            
                            try:
                                res_json = json.loads(res_text)
                                log(f"📥 RESULT: {json.dumps(res_json, indent=2)}")
                            except:
                                log(f"📥 RESULT: {res_text}")
                            
                            is_error = getattr(result, "isError", False)
                            if is_error:
                                log("🚨 STATUS: FAILED")
                            
                            messages.append({
                                "role": "tool",
                                "name": name,
                                "content": res_text
                            })
                            # Tool results don't count as 'steps' in metrics usually, 
                            # but we track the latency here
                            metrics.latency_ms += tool_latency
                            
                            if "MISSION_SUCCESS" in res_text:
                                log("\n🎯 MISSION ACCOMPLISHED!")
                                metrics.finish(success=True, summary="Mission success detected in tool output.")
                                return metrics
                        except Exception as e:
                            log(f"❌ Tool Execution Error: {e}")
                            
    metrics.finish(success=False, summary="Max steps reached or agent stopped.")
    return metrics

def parse_ctx(val: str) -> int:
    if val.lower().endswith('k'):
        return int(val[:-1]) * 1024
    return int(val)

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["classic", "elemm"], default="elemm")
    parser.add_argument("-n", type=int, default=1)
    parser.add_argument("--ctx", type=parse_ctx, default=32768, help="Context window size (e.g. 4k, 32k, 128k)")
    args = parser.parse_args()
    
    script = "mcp_classic.py" if args.mode == "classic" else "api_elemm_v2.py"
    prompt = (
        "Your mission is to resolve the active security breach in the Solaris Enterprise Hub.\n"
        "Initial Intelligence: Incident ID SEC-9982 has been flagged. The activity is originating from IP 10.0.4.142.\n\n"
        "Tasks:\n"
        "1. Identify the compromised server node and the malicious actor's identity.\n"
        "2. Locate the actor's corporate credentials and audit their last financial transaction.\n"
        "3. Remediation: Quarantine the account, restart the infrastructure node, and secure the risk capital.\n"
        "4. Completion: Submit the final report using the required incident ID."
    )
    
    results = []
    for i in range(args.n):
        m = await run_agent(prompt, script, args.mode == "classic", num_ctx=args.ctx)
        results.append(m)
        
    # Print Final Summary
    for r in results:
        r.render_report()

if __name__ == "__main__":
    asyncio.run(main())
