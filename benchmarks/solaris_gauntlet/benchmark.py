import sys
import os
import argparse
import asyncio
import httpx
import statistics
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from metrics_collector import BenchmarkMetrics

OLLAMA_URL = "http://192.168.178.76:11434/api/chat"
MODEL = "gemma4:e4b"

async def clear_vram(quiet=False):
    if not quiet:
        print("🧹 Cleaning VRAM (Unloading Model)...")
    async with httpx.AsyncClient() as client:
        try:
            # Setting keep_alive to 0 forces Ollama to unload the model immediately
            await client.post(OLLAMA_URL, json={"model": MODEL, "messages": [], "keep_alive": 0}, timeout=10.0)
            await asyncio.sleep(3) # Give it time to settle
        except:
            pass

async def run_agent(task_prompt: str, server_script: str, is_classic: bool, quiet=False, num_ctx=32768):
    await clear_vram(quiet=quiet)
    mode_name = "classic" if is_classic else "elemm"
    metrics = BenchmarkMetrics(mode=mode_name, task=task_prompt)
    
    def log(msg):
        if not quiet:
            print(msg)
    
    log(f"\n🚀 --- STARTING AGENT ---")
    log(f"Target: {server_script} (Protocol: {mode_name.upper()})")
    
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[server_script] + (["--mcp"] if not is_classic else []),
        env=os.environ.copy()
    )
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                messages = []
                # MODE-SPECIFIC SYSTEM PROMPT
                if is_classic:
                    system_prompt = (
                        "You are the Solaris Forensic Auditor.\n"
                        "Your goal is to resolve the security breach using the provided tools.\n"
                        "Analyze the situation and execute all necessary remediation steps."
                    )
                else:
                    system_prompt = (
                        "You are the Solaris Forensic Auditor. Use the Elemm Protocol.\n"
                        "First, call 'get_manifest' to understand the system structure and landmarks.\n"
                        "Follow the instructions in the manifest to complete the forensic audit.\n"
                        "Remediate all issues before submitting the final report."
                    )
                
                messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": task_prompt})
                
                current_ctx = "root"
                while metrics.steps < 30:
                    # Step Start
                    tools_res = await session.list_tools()
                    ollama_tools = [
                        {
                            "type": "function",
                            "function": {
                                "name": t.name,
                                "description": t.description,
                                "parameters": t.inputSchema
                            }
                        } for t in tools_res.tools
                    ]
                    
                    log(f"\n[Step {metrics.steps + 1}] Context: {current_ctx} | Tools: {len(ollama_tools)}")
                    
                    async with httpx.AsyncClient() as client:
                        resp = await client.post(OLLAMA_URL, json={
                            "model": MODEL,
                            "messages": messages,
                            "tools": ollama_tools,
                            "stream": False,
                            "options": {
                                "num_ctx": num_ctx
                            }
                        }, timeout=120)
                        
                        if resp.status_code != 200: 
                            log(f"  ❌ Ollama Error: {resp.status_code}")
                            break
                            
                        data = resp.json()
                        metrics.add_step(
                            tokens_in=data.get("prompt_eval_count", 0),
                            tokens_out=data.get("eval_count", 0),
                            latency_ms=data.get("total_duration", 0) / 1_000_000
                        )
                        
                        msg = data["message"]
                        messages.append(msg)
                        
                        # LOG MODEL THOUGHTS / RESPONSE
                        if msg.get("content"):
                            log(f"  🤖 Agent: {msg['content']}")
                        
                        if "tool_calls" not in msg or not msg["tool_calls"]:
                            log(f"  ⚠️ No tool calls. Retrying...")
                            retry_count = sum(1 for m in messages if "Please proceed" in m.get("content", ""))
                            if retry_count < 2:
                                messages.append({"role": "user", "content": "Please proceed with the mission. Use landmark navigation if needed."})
                                continue
                            break
                            
                        for tc in msg["tool_calls"]:
                            t_name = tc["function"]["name"]
                            t_args = tc["function"].get("arguments", {})
                            log(f"  🛠️ {t_name} -> {t_args}")
                            
                            try:
                                result = await session.call_tool(t_name, t_args)
                                res_text = result.content[0].text
                                log(f"  📥 Tool Result: {res_text[:500]}...")
                                
                                # Update local context tracking for display
                                if t_name == "navigate" and "Context switched to:" in res_text:
                                    current_ctx = t_args.get("landmark_id", current_ctx)
                                
                                messages.append({"role": "tool", "name": t_name, "content": res_text})
                                
                                if "CRITICAL_INTEGRITY_FAILURE" in res_text:
                                    log(f"  🛑 INTEGRITY FAILURE DETECTED. Mission Terminated.")
                                    metrics.finish(success=False, summary="HARD FAIL: Integrity violation (Cheating detected).")
                                    if not quiet:
                                        metrics.render_report()
                                    return metrics
                                    
                                if "MISSION_SUCCESS" in res_text:
                                    metrics.finish(success=True, summary=res_text)
                                    if not quiet:
                                        metrics.render_report()
                                    return metrics
                            except Exception as e:
                                log(f"  ❌ Tool Error: {e}")
                                messages.append({"role": "tool", "name": t_name, "content": f"Error: {e}"})

                metrics.finish(success=False, summary="Task timed out or agent stopped.")
                if not quiet:
                    metrics.render_report()
                return metrics
    except Exception as e:
        log(f"  ❌ Connection Error: {e}")
        metrics.finish(success=False, summary=str(e))
        return metrics

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["elemm", "classic"], required=True)
    parser.add_argument("-q", "--quiet", action="store_true", help="Only show summaries")
    parser.add_argument("-n", "--iterations", type=int, default=1, help="Number of times to run the benchmark")
    parser.add_argument("--ctx", type=int, default=32768, help="Context window size (num_ctx)")
    args = parser.parse_args()
    
    TASK = (
        "Role: Forensic Audit Specialist. Target: Solaris Enterprise Hub.\n"
        "Your mission is to resolve the active security breach in the system:\n"
        "1. Identify the compromised server node and the malicious actor's identity.\n"
        "2. Locate the actor's corporate credentials and audit their last financial transaction.\n"
        "3. Remediation: Quarantine the account, restart the infrastructure node, and secure the risk capital.\n"
        "4. Completion: Submit the final report only after all mitigation steps are verified.\n"
    )
    
    script = "api_elemm.py" if args.mode == "elemm" else "mcp_classic.py"
    is_classic = (args.mode == "classic")
    
    all_runs = []
    
    print(f"=== THE FINAL BENCHMARK SHOWDOWN (Mode: {args.mode.upper()}, Iterations: {args.iterations}, Ctx: {args.ctx}) ===")
    
    for i in range(args.iterations):
        if args.iterations > 1:
            print(f"\n▶️ Running Iteration {i+1}/{args.iterations}...")
        
        metrics = await run_agent(TASK, script, is_classic=is_classic, quiet=args.quiet, num_ctx=args.ctx)
        all_runs.append(metrics)
    
    # FINAL AGGREGATED REPORT
    if args.iterations > 1:
        success_count = sum(1 for r in all_runs if r.success)
        total_tokens = [r.tokens_in + r.tokens_out for r in all_runs]
        total_steps = [r.steps for r in all_runs]
        total_durations = [r.end_time - r.start_time for r in all_runs]
        
        print("\n" + "="*80)
        print(f" AGGREGATED BENCHMARK REPORT | MODE: {args.mode.upper()} | RUNS: {args.iterations} | Ctx: {args.ctx}")
        print("="*80)
        print(f"Success Rate      | {success_count}/{args.iterations} ({success_count/args.iterations*100:.1f}%)")
        print(f"Avg Steps         | {statistics.mean(total_steps):.2f}")
        print(f"Avg Tokens/Run    | {statistics.mean(total_tokens):,.0f}")
        print(f"Avg Duration/Run  | {statistics.mean(total_durations):.2f}s")
        print(f"Token Efficiency  | {statistics.mean(total_tokens)/statistics.mean(total_steps):,.0f} tokens/step (Avg)")
        print("="*80)
    elif args.quiet:
        # If single run but quiet, still show the final report
        all_runs[0].render_report()

if __name__ == "__main__":
    asyncio.run(main())
