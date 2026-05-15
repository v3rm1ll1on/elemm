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

from typing import Any, Dict, Optional

class SecurityPolicy:
    """Policy Engine to enforce security restrictions on landmarks and actions."""
    def __init__(self, config: Dict[str, Any]):
        self.policy = config.get("security", {})
        self.disallowed_patterns = [p.lower() for p in self.policy.get("disallowed_patterns", [])]
        self.allowed_methods = [m.upper() for m in self.policy.get("allowed_methods", [])]
        self.disallowed_landmarks = [l.lower() for l in self.policy.get("disallowed_landmarks", [])]
        self.disallowed_actions = [a.lower() for a in self.policy.get("disallowed_actions", [])]

    def is_action_allowed(self, action_id: str, method: Optional[str] = None) -> Dict[str, Any]:
        """
        Checks if an action is allowed based on the current policy.
        Returns {'allowed': True} or {'allowed': False, 'reason': '...', 'remedy': '...'}
        """
        # Exempt Core Tools and internal inspection checks from Policy
        if action_id.startswith("elemm:") or action_id in ["connect_to_site", "get_manifest", "get_landmarks", "inspect_landmark", "list_aliases", "clear_session"]:
            return {"allowed": True}

        action_lower = action_id.lower()
        
        # 1. Check HTTP Method (if provided and restricted)
        if method and self.allowed_methods:
            method_upper = method.upper()
            if method_upper not in self.allowed_methods:
                return {
                    "allowed": False,
                    "reason": f"HTTP method '{method_upper}' is restricted by security policy.",
                    "remedy": f"Only the following methods are permitted: {', '.join(self.allowed_methods)}"
                }

        # 2. Check Explicit Action Blacklist
        if action_lower in self.disallowed_actions:
            return {
                "allowed": False,
                "reason": f"Action '{action_id}' is explicitly blacklisted.",
                "remedy": "Contact your administrator to request access to this specific endpoint."
            }

        # 3. Check Landmark Blacklist (Colon is primary separator, underscore is fallback)
        landmark = action_id.split(":", 1)[0] if ":" in action_id else (action_id.split("_", 1)[0] if "_" in action_id else action_id)
        if landmark.lower() in self.disallowed_landmarks:
            return {
                "allowed": False,
                "reason": f"Landmark area '{landmark}' is restricted.",
                "remedy": f"Access to the '{landmark}' functional area is disabled in this gateway instance."
            }

        # 4. Check Patterns (e.g. 'delete')
        for pattern in self.disallowed_patterns:
            if pattern in action_lower:
                return {
                    "allowed": False,
                    "reason": f"Action contains restricted pattern '{pattern}'.",
                    "remedy": "Destructive operations are disabled by default. Use read-only or safe alternatives."
                }

        return {"allowed": True}
