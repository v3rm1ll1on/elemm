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

async def run_agent(task_prompt: str, server_script: str, is_classic: bool, quiet=False, num_ctx=32768, log_file=None):
    mode_name = "classic" if is_classic else "elemm"
    metrics = BenchmarkMetrics(mode=mode_name, task=task_prompt)
    
    def log(msg):
        if not quiet:
            print(msg)
        if log_file:
            log_file.write(str(msg) + "\n")

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
                            metrics.add_nudge()
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
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress step-by-step output")
    parser.add_argument("-s", "--silent", action="store_true", help="Alias for --quiet")
    parser.add_argument("-o", "--output", help="Write full log to this file")
    args = parser.parse_args()
    
    is_quiet = args.quiet or args.silent
    log_file = open(args.output, "w") if args.output else None
    
    if is_quiet:
        import logging
        logging.basicConfig(level=logging.ERROR)
        logging.getLogger().setLevel(logging.ERROR)
        logging.getLogger("elemm").setLevel(logging.ERROR)
        logging.getLogger("mcp").setLevel(logging.ERROR)
        logging.captureWarnings(True)
        logging.getLogger("py.warnings").setLevel(logging.ERROR)
    
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
        run_header = f"\n🚀 STARTING RUN {i+1}/{args.n}..."
        if not is_quiet:
            print(run_header)
        if log_file:
            log_file.write(run_header + "\n")
            
        m = await run_agent(prompt, script, args.mode == "classic", quiet=is_quiet, num_ctx=args.ctx, log_file=log_file)
        
        # Capture report output
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            m.render_report()
        report_str = f.getvalue()
        
        print(report_str) # Always print to console
        if log_file:
            log_file.write(report_str + "\n")
            
        results.append(m)
        
    # Print Final Aggregate Summary
    if args.n > 1:
        summary_lines = []
        summary_lines.append("\n" + "#"*80)
        summary_lines.append(f" AGGREGATED SUMMARY | {args.n} RUNS | MODE: {args.mode.upper()}")
        summary_lines.append("#"*80)
        
        success_count = sum(1 for r in results if r.success)
        total_in = sum(r.tokens_in for r in results)
        total_out = sum(r.tokens_out for r in results)
        avg_steps = sum(r.steps for r in results) / args.n
        avg_nudges = sum(r.nudges for r in results) / args.n
        avg_in = total_in / args.n
        avg_out = total_out / args.n
        avg_peak = sum(r.total_context_tokens for r in results) / args.n
        avg_dur = sum(r.end_time - r.start_time for r in results) / args.n
        
        # Calculate Total Cost (Reference: Gemini 3.1 Pro prices)
        total_cost_pro = (total_in / 1_000_000 * 2.00) + (total_out / 1_000_000 * 12.00)

        summary_lines.append(f"Success Rate      | {success_count}/{args.n} ({success_count/args.n*100:.1f}%)")
        summary_lines.append(f"Avg Steps         | {avg_steps:.2f}")
        summary_lines.append(f"Avg Nudges        | {avg_nudges:.2f}")
        summary_lines.append(f"Avg Tokens In     | {avg_in:.1f}")
        summary_lines.append(f"Avg Tokens Out    | {avg_out:.1f}")
        summary_lines.append(f"Avg Peak Context  | {avg_peak:.1f}")
        summary_lines.append(f"Avg Duration (s)  | {avg_dur:.2f}")
        summary_lines.append("#"*80)

        summary_lines.append("\n" + "-"*40)
        summary_lines.append(f" 💰 AGGREGATED COST ANALYSIS ({args.n} RUNS)")
        summary_lines.append("-"*40)
        summary_lines.append(f"Total Tokens In   | {total_in}")
        summary_lines.append(f"Total Tokens Out  | {total_out}")
        summary_lines.append("-" * 40)
        summary_lines.append(f"{'Model':<25} | {'Total Cost':<10}")
        summary_lines.append("-" * 40)
        
        prices = {
            "Gemini 3.1 Flash-Lite": (0.25, 1.50),
            "Gemini 3.1 Pro":        (2.00, 12.00),
            "GPT-5.4 mini":          (0.75, 4.50),
            "GPT-5.5 / Claude Opus": (5.00, 30.00),
        }
        for model, (p_in, p_out) in prices.items():
            cost = (total_in / 1_000_000 * p_in) + (total_out / 1_000_000 * p_out)
            summary_lines.append(f"{model:<25} | ${cost:.6f}")
        summary_lines.append("-" * 40 + "\n")
        
        summary_str = "\n".join(summary_lines)
        print(summary_str)
        if log_file:
            log_file.write(summary_str + "\n")

    if log_file:
        log_file.close()

if __name__ == "__main__":
    asyncio.run(main())
