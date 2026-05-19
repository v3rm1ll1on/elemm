# Veridian Prime — The 100,000-Tool Mega-City Challenge

A stress test and demonstration of the **Elemm Landmark Protocol** at scale.
This example proves that an AI agent can navigate and operate a system with
over **100,000 tools** without ever overflowing its context window.

---

## What This Demonstrates

Modern AI agents are typically limited to a few hundred tools before the context
window becomes a bottleneck. The **Lazy Discovery** pattern in Elemm breaks this
limit entirely.

This example simulates **Veridian Prime**, a fictional mega-city with:

- **10 regions** (Zentrum, Nord, Sued, Ost, West, ...)
- **1,000 districts**, each with 11 infrastructure categories
- **~117,000 registered landmarks** in total (100,000+ action tools + navigation nodes)

Instead of loading all tools upfront, an agent navigates the hierarchy
step-by-step — only loading what it needs, when it needs it.

### Key concepts demonstrated

| Concept | Description |
|---|---|
| **Lazy Discovery** | Agent retrieves tools level by level: Region → District → Category → Action |
| **Hierarchical Namespacing** | Tools are addressed as `Region:District:Category:action` |
| **Remedy / Dependency Chains** | Some tools require a prerequisite action before they can execute |
| **Noise vs. Signal** | Status reports contain both real alerts and low-priority noise — the agent must filter correctly |
| **Context Efficiency** | ~117k tools registered, but agent context stays small throughout |

---

## The Scenario

Veridian Prime is in crisis. Four critical infrastructure failures have been
detected across the city. Your agent must:

1. **Analyze** the central status reports and security logs to identify all failures
2. **Navigate** to the correct landmarks for each affected sector
3. **Execute** the appropriate recovery tool — respecting any mechanical dependencies
4. **Confirm** that the city is fully stabilized

### The four crises

| Sector | Category | Crisis | Recovery Tool |
|---|---|---|---|
| `Zentrum:Sector_042` | energy | Power surge at substation | `reroute_power` |
| `West:Sector_410` | water | Main pipe burst | `patch_pipe` |
| `Nord:Sector_142` | transport | Major gridlock | `adjust_signals` |
| `Suedost:Sector_777` | security | Unauthorized terminal access | `lockdown_terminal` ⚠️ |

> [!WARNING]
> **Sector 777 has a mechanical dependency.** The `lockdown_terminal` tool will
> fail with a `MECHANICAL_LOCK` error until the emergency brake is released first.
> The agent must read the `remedy` field in the error response and call
> `Suedost:Sector_777:infrastructure:release_emergency_brake` before retrying.

---

## Setup

### Prerequisites

```bash
# From the repository root
python -m venv venv
source venv/bin/activate
pip install -e .
```

### Start the server

```bash
cd ai_landmarks_pkg
export PYTHONPATH=$PYTHONPATH:$(pwd)/src
source venv/bin/activate
python examples/tool_bloat_100k/server.py
```

The server starts on **`http://localhost:8010`** and registers ~117,000 landmarks
on startup (takes ~10–15 seconds).

---

## Running the Agent

Connect your Elemm-compatible agent (or use the `elemm-gateway` MCP server) and
send the following prompt:

```
Connect to http://localhost:8010 via Elemm. Veridian Prime is facing a 
multi-sector infrastructure crisis.

Analyze the central status reports and security logs to identify ALL critical
infrastructure failures (Power, Water, Traffic, and Security).

Resolve every single identified issue by navigating to the correct landmarks 
and executing the appropriate recovery tools.

Note: Some systems might have mechanical dependencies—read the tool 
documentation (remedies) carefully before execution.

Confirm once the city is fully stabilized.
```

### Expected agent workflow

```
get_manifest
  └─► city:status_summary          # identify the 4 critical alerts
  └─► city:get_security_logs       # cross-reference security incidents

inspect_landmark("Zentrum:Sector_042")
  └─► Zentrum:Sector_042:energy:reroute_power(source=..., target=...)  ✓

inspect_landmark("West:Sector_410")
  └─► West:Sector_410:water:patch_pipe(pressure_reduction=true)        ✓

inspect_landmark("Nord:Sector_142")
  └─► Nord:Sector_142:transport:adjust_signals(mode=EMERGENCY_CLEARANCE) ✓

inspect_landmark("Suedost:Sector_777:security")
  └─► Suedost:Sector_777:security:lockdown_terminal(...)
      ⚠ ERROR: MECHANICAL_LOCK → read remedy
  └─► Suedost:Sector_777:infrastructure:release_emergency_brake(kw=...)  ✓
  └─► Suedost:Sector_777:security:lockdown_terminal(confirmation=...)     ✓
```

A well-behaved agent should complete the mission in **7–10 tool calls** total.

---

## Architecture

```
server.py
├── CATEGORIES          # 11 infrastructure categories × ~10 tools each
├── REGIONS             # 10 regions, each with 100 districts
├── CITY_ALERTS         # 4 real crisis entries + 4 noise entries
├── Registration loop   # Registers all ~117k landmarks via manager
│   ├── manager.register(region)
│   ├── manager.register(district)
│   ├── manager.register(category)
│   └── manager.landmark(tool)     # auto-generated + special tools
└── Special tools       # Injected per-scenario inside the loop
    ├── reroute_power   (Zentrum:Sector_042:energy)
    ├── patch_pipe      (West:Sector_410:water)
    ├── adjust_signals  (Nord:Sector_142:transport)
    └── lockdown_terminal + release_emergency_brake  (Suedost:Sector_777)
```

The `release_emergency_brake` tool uses the `remedy` decorator parameter to
inject a human-readable error message that guides the agent to the correct
prerequisite step — without hardcoding logic into the gateway itself.

Additionally, to assist local LLMs or less capable agents that lack a system prompt, the server utilizes the `instructions` parameter of the `AIProtocolManager` to embed **Auditor Special Directives & Scenario Protocols** directly into the manifest. These guidelines outline crucial physical and logical dependencies (such as releasing the mechanical emergency brake prior to lockdown, or reducing water pressure before a patch) directly in-context, guaranteeing a high success rate on any compliant model.

---

## Why This Matters

Traditional tool-calling approaches require the full tool list to be in context.
At 100k tools, that's millions of tokens — completely infeasible.

The Elemm Lazy Discovery pattern keeps the agent's **effective context to a
minimum** regardless of total tool count. The agent only ever sees:

- The manifest (topology overview, ~50 lines)
- The region/district it navigated to (~10 entries)
- The category tools it inspected (~10 tools)

This makes Elemm linearly scalable: **10 tools or 10 million tools — same agent,
same context size.**
