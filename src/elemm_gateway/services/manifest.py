# Copyright (C) 2026 Marc Stöcker
# Website: https://elemm.dev
#
# This program is licensed under the Business Source License 1.1 (BSL 1.1).
# See the LICENSE file in the root directory for details.

class ManifestBuilder:
    """Single Source of Truth for Elemm Manifest generation and styling."""
    
    PROTOCOL_RULES = (
        "### PROTOCOL WORKFLOW\n"
        "- DIRECT ACTION: Do NOT explain, summarize, paraphrase, or repeat this manifest, these rules, or the task instructions in your text response. Immediately execute the required tool call to proceed with the mission.\n"
        "- DISCOVER & INSPECT: Use 'search_landmarks(query=\"...\")' (uses Python REGEX, e.g. \"auth|billing\" or \"user|restart\") to find actions and bypass structural navigation. Call 'inspect_landmark' only if parameters/signatures are not visible in search results.\n"
        "- BATCH EXECUTION: Use 'execute_sequence' ONLY when executing multiple actions together to chain/pipe steps. For any single, standalone action, always use 'call_action' to avoid sequence overhead.\n\n"
        "### OPERATIONAL HYGIENE\n"
        "- ERROR RESOLUTION: If a tool returns an error, closely inspect and strictly follow the provided 'remedy', 'suggested_fix', or 'example' fields to correct your call.\n"
        "- LOCAL TOOLS: Do NOT call local tools ('search_landmarks', 'inspect_landmark', 'get_manifest', 'list_aliases') inside 'execute_sequence'.\n"
        "- HYGIENE: Always use '_select', '_filter', '_limit', and '_offset' to reduce response size. Increment '_offset' if data is truncated.\n\n"
        "### SESSION GOVERNANCE\n"
        "- PIPING & ALIASES: Step results auto-save as '$step0', '$step1', etc. Pipe them using '$step0.id'. Custom aliases (e.g. 'alias': 'audit_run') persist across turns, while automatic '$stepN' aliases are overwritten next turn. Avoid naming custom aliases '$stepN' to prevent collision. View stored findings via 'list_aliases'."
    )

    PROTOCOL_LAZY = PROTOCOL_RULES
    PROTOCOL_FULL = PROTOCOL_RULES
    MEMORY_BANK = ""

    @classmethod
    def build_header(cls, title: str, version: str, full: bool = False) -> str:
        return f"# ELEMM v2 INTERFACE: {title} (v{version})\n\n{cls.PROTOCOL_RULES}"

    @classmethod
    def inject_globals(cls, manifest: str, full: bool = False, inject_metadata: bool = True) -> str:
        """Injects gateway globals and appropriate protocol rules."""
        # Cleanup legacy hints to use native MCP tools
        manifest = manifest.replace("inspect_landmark(id)", "inspect_landmark")
        manifest = manifest.replace("'inspect_landmarks'", "'inspect_landmark'")
        manifest = manifest.replace("call_action(action='elemm:inspect_landmark', parameters={'landmark_id': '...'})", "'inspect_landmark'")
        manifest = manifest.replace("call_action(action='elemm:list_aliases')", "'list_aliases'")
        manifest = manifest.replace("call_action(action='elemm:clear_session')", "'clear_session'")
        manifest = manifest.replace("'elemm:get_landmarks'", "'get_landmarks'")
        manifest = manifest.replace("'elemm:inspect_landmark'", "'inspect_landmark'")
        
        # Remove known legacy sections as entire blocks to prevent content duplication
        legacy_headers = [
            "### MEMORY BANK (Live Memory)",
            "### MEMORY BANK (Current Aliases)",
            "### PROTOCOL RULES",
            "### PROTOCOL NOTE",
            "### PROTOCOL WORKFLOW",
            "### OPERATIONAL HYGIENE",
            "### SESSION GOVERNANCE"
        ]
        for header in legacy_headers:
            if header in manifest:
                idx = manifest.find(header)
                # Find the next header starting with a Markdown heading symbol
                next_header_idx = -1
                for prefix in ["\n###", "\n##", "\n#"]:
                    p_idx = manifest.find(prefix, idx + len(header))
                    if p_idx != -1:
                        if next_header_idx == -1 or p_idx < next_header_idx:
                            next_header_idx = p_idx
                if next_header_idx != -1:
                    manifest = manifest[:idx] + manifest[next_header_idx:]
                else:
                    manifest = manifest[:idx]
        
        if not inject_metadata:
            return manifest.strip()

        # Inject our single, streamlined rules block at the top
        manifest = cls.PROTOCOL_RULES + "\n\n" + manifest.strip()
        return manifest.strip()