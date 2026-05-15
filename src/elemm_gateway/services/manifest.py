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
        "1. DISCOVER: Call 'get_landmarks' to find functional areas.\n"
        "2. INSPECT: Call 'inspect_landmark' to get technical signatures (REQUIRED before execution).\n"
        "   - NOTE: You can inspect multiple areas at once: `landmark_id=['area1', 'area2']`.\n"
        "3. EXECUTE: Use 'execute_sequence' (batching) or action names directly.\n\n"
        "### BATCHING & PIPING\n"
        "- Use 'execute_sequence' to chain tools: `actions=[{'action': 'A', 'alias': 'res'}, {'action': 'B', 'parameters': {'id': '$res.id'}}]`.\n\n"
        "### OPERATIONAL HYGIENE\n"
        "- HYGIENE: Use '_select', '_filter', and '_limit' in large requests to prevent context overflow.\n\n"
        "### CRITICAL RULES\n"
        "- ANTI-PATTERN: NEVER guess action names or parameter schemas from memory.\n"
        "- FIDELITY: Signatures vary per site. Only 'inspect_landmark' is ground truth.\n"
    )

    PROTOCOL_FULL = (
        "### PROTOCOL WORKFLOW\n"
        "- DISCOVER: Call 'get_landmarks' to find functional areas.\n"
        "- INSPECT: Call 'inspect_landmark' to get technical signatures (REQUIRED before execution).\n"
        "- EXECUTE: Use 'execute_sequence' (batching) or action names directly.\n\n"
        "### BATCHING EXAMPLE\n"
        "```json\n"
        "execute_sequence(actions=[\n"
        "  {\"action\": \"city:get_logs\", \"alias\": \"logs\", \"parameters\": {\"_limit\": 1}},\n"
        "  {\"action\": \"city:analyze\", \"parameters\": {\"target\": \"$logs[0].id\"}}\n"
        "])\n"
        "```\n\n"
        "### OPERATIONAL HYGIENE\n"
        "- HYGIENE: Use '_select', '_filter', and '_limit' in EVERY call to prevent context overflow.\n"
        "- PIPING: Chain results via '$alias.field' (e.g. '$step0.id') in any parameter.\n"
    )

    PROTOCOL_RULES = PROTOCOL_LAZY

    MEMORY_BANK = (
        "### SESSION GOVERNANCE\n"
        "- Use 'list_aliases' to see all current session findings ($step0, $step1, etc.).\n"
        "- PIPING: Chain results via '$alias.field' (e.g. '$step0.id') in any parameter.\n"
        "- ISOLATION: Findings are stored for the duration of the 'session_id'.\n"
        "- CLEANUP: Call 'clear_session' after task completion for privacy.\n"
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
