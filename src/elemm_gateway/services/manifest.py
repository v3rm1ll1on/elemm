# Copyright (C) 2026 Marc Stöcker
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

class ManifestBuilder:
    """Single Source of Truth for Elemm Manifest generation and styling."""
    
    PROTOCOL_LAZY = (
        "### PROTOCOL WORKFLOW\n"
        "1. DISCOVER: If you have a specific symptom/keyword (e.g. 'alarm', 'leak'), bypass structural navigation and use 'search_landmarks' directly (supports Python REGEX & returns direct actions!). Otherwise, call 'get_landmarks'.\n"
        "2. INSPECT: Call 'inspect_landmark' to get technical signatures (REQUIRED before execution). Tip: You can inspect single actions directly.\n"
        "3. PLAN: Proactively write down all identified issues, map each to its corresponding action and technical parameters.\n"
        "4. EXECUTE: Fire them in ONE single 'execute_sequence' batch rather than sequential step-by-step calls.\n\n"
        "### OPERATIONAL HYGIENE\n"
        "- PLANNING: Before execution, list all issues, map them to actions+parameters, and execute them in ONE single 'execute_sequence' batch. Never work reactively step-by-step.\n"
        "- SHORTCUTS: Bypass structural navigation! If you are hunting a specific issue, call 'search_landmarks(query=\"alarm|leak\")' first (uses Python REGEX). It searches both landmarks and actions globally, saving >90% context.\n"
        "- LOCAL TOOLS: 'search_landmarks', 'inspect_landmark', 'get_landmarks', and 'get_manifest' are local gateway tools and CANNOT be used within 'execute_sequence'. Only remote site actions (e.g. 'Landmark:action') are valid targets.\n"
        "- PATH ADDRESSING: Sibling or sub-landmark paths mentioned in logs/alerts map directly to addressable landmarks. Call 'inspect_landmark' on them directly. Sibling actions may have prerequisite preconditions (e.g. locks/releases) within the same sub-landmark.\n"
        "- BATCHING: For independent actions, always prefer 'execute_sequence' over sequential 'call_action' calls. Failures are isolated per step.\n"
        "- ONBOARDING: New to this system? Run call_action(action='_elemm-help') before your first execute_sequence call.\n"
        "- HYGIENE: Use '_select', '_filter', '_limit', and '_offset' to manage context overflow.\n"
        "- VIRTUAL PAGINATION: If results are truncated, use '_offset' to fetch the next page. This works on BOTH lists and large string content (logs).\n"
    )

    PROTOCOL_FULL = (
        "### PROTOCOL WORKFLOW\n"
        "- DISCOVER: If you have a specific symptom/keyword (e.g. 'alarm', 'leak'), bypass structural navigation and use 'search_landmarks' directly (supports Python REGEX & returns direct actions!). Otherwise, call 'get_landmarks'.\n"
        "- INSPECT: Call 'inspect_landmark' to get technical signatures (REQUIRED before execution). Tip: You can inspect single actions directly.\n"
        "- PLAN: Proactively write down all identified issues, map each to its corresponding action and technical parameters.\n"
        "- EXECUTE: Fire them in ONE single 'execute_sequence' batch rather than sequential step-by-step calls.\n\n"
        "### OPERATIONAL HYGIENE\n"
        "- PLANNING: Before execution, list all issues, map them to actions+parameters, and execute them in ONE single 'execute_sequence' batch. Never work reactively step-by-step.\n"
        "- SHORTCUTS: Bypass structural navigation! If you are hunting a specific issue, call 'search_landmarks(query=\"alarm|leak\")' first (uses Python REGEX). It searches both landmarks and actions globally, saving >90% context.\n"
        "- LOCAL TOOLS: 'search_landmarks', 'inspect_landmark', 'get_landmarks', and 'get_manifest' are local gateway tools and CANNOT be used within 'execute_sequence'. Only remote site actions (e.g. 'Landmark:action') are valid targets.\n"
        "- PATH ADDRESSING: Sibling or sub-landmark paths mentioned in logs/alerts map directly to addressable landmarks. Call 'inspect_landmark' on them directly. Sibling actions may have prerequisite preconditions (e.g. locks/releases) within the same sub-landmark.\n"
        "- BATCHING: For independent or sequential actions, always prefer 'execute_sequence' over sequential 'call_action' calls. Failures are isolated per step.\n"
        "- ONBOARDING: New to this system? Run call_action(action='_elemm-help') before your first execute_sequence call.\n"
        "- HYGIENE: Use '_select', '_filter', '_limit', and '_offset' in EVERY call to prevent context overflow.\n"
        "- VIRTUAL PAGINATION: This gateway supports virtual pagination for ALL tools. If a response is truncated, increment '_offset' to see the remaining data.\n"
        "- PIPING: Chain results via '$alias.field' (e.g. '$step0.id') in any parameter. **IMPORTANT: $stepN is local to the current call and overwritten in the next sequence.** Use custom aliases for global persistence.\n"
    )

    PROTOCOL_RULES = PROTOCOL_LAZY

    MEMORY_BANK = (
        "### SESSION GOVERNANCE\n"
        "- Use 'list_aliases' to see all current session findings ($step0, $step1, etc.).\n"
        "- PERSISTENCE: Custom aliases (e.g. 'alias: \"user_id\"') stay in memory across turns.\n"
        "- VOLATILITY: '$stepN' aliases are overwritten in each 'execute_sequence' call. Always prefer custom aliases for critical data.\n"
        "- SYNTAX: Use '$alias.field' (e.g. '$step0.id') or '$alias[0].field'. Do NOT use '.result' in the path.\n"
    )

    @classmethod
    def build_header(cls, title: str, version: str, full: bool = False) -> str:
        rules = cls.PROTOCOL_FULL if full else cls.PROTOCOL_LAZY
        return f"# ELEMM v2 INTERFACE: {title} (v{version})\n\n{rules}\n{cls.MEMORY_BANK}"

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
        
        # Remove known legacy sections to prevent duplication
        manifest = manifest.replace("### PROTOCOL NOTE", "")
        manifest = manifest.replace("### PROTOCOL RULES", "")
        
        if not inject_metadata:
            return manifest.strip()

        rules = cls.PROTOCOL_FULL if full else cls.PROTOCOL_LAZY
        
        # Inject Protocol Rules if missing or outdated
        has_new_rules = "PROTOCOL WORKFLOW" in manifest
        if not has_new_rules:
            # Append rules at the top if they are missing
            manifest = rules + "\n" + manifest

        # Inject Memory Bank if missing or outdated
        has_new_memory = "SESSION GOVERNANCE" in manifest
        if not has_new_memory:
            # Avoid duplicating old memory bank headers if they still exist
            manifest = manifest.replace("### MEMORY BANK (Live Memory)", "")
            manifest = manifest.replace("### MEMORY BANK (Current Aliases)", "")
            manifest = manifest + "\n\n" + cls.MEMORY_BANK

        return manifest.strip()
