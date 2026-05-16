import re
import logging
from typing import Any, Dict, Optional, List, Union

logger = logging.getLogger("elemm-gateway")

class SecurityPolicy:
    """
    Advanced Policy Engine (Guardian) to enforce security restrictions.
    Supports Blacklisting, Whitelisting, Regex Patterns, and Deep Argument Inspection.
    """
    def __init__(self, config: Dict[str, Any]):
        self.refresh(config)

    def refresh(self, config: Dict[str, Any]):
        """Updates the policy attributes from the given configuration."""
        self.policy = config.get("security", {})
        
        # 1. Mode Settings
        self.enforce_whitelist = self.policy.get("enforce_whitelist", False)
        
        # 2. Blacklists
        self.disallowed_landmarks = [l.lower() for l in self.policy.get("disallowed_landmarks", [])]
        self.disallowed_actions = [a.lower() for a in self.policy.get("disallowed_actions", [])]
        
        # 3. Whitelists
        self.allowed_landmarks = [l.lower() for l in self.policy.get("allowed_landmarks", [])]
        self.allowed_actions = [a.lower() for a in self.policy.get("allowed_actions", [])]
        self.allowed_methods = [m.upper() for m in self.policy.get("allowed_methods", ["GET", "POST", "PUT", "PATCH", "DELETE"])]
        
        # 4. Patterns (Compiled Regex Support)
        self.patterns = []
        for p in self.policy.get("disallowed_patterns", []):
            if p.startswith("re:"):
                try:
                    self.patterns.append({"type": "regex", "val": re.compile(p[3:], re.IGNORECASE), "raw": p})
                except Exception as e:
                    logger.error(f"Security: Invalid regex pattern '{p}': {e}")
            else:
                self.patterns.append({"type": "simple", "val": p.lower(), "raw": p})
                
        # 5. Custom Remedies
        self.remedies = self.policy.get("custom_remedies", {})

    def _get_remedy(self, key: str, default: str) -> str:
        """Returns a custom remedy message if defined, otherwise the default."""
        return self.remedies.get(key, default)

    def is_action_allowed(self, action_id: str, method: Optional[str] = None, arguments: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Comprehensive security check for an action.
        Checks: Whitelist -> Blacklist -> Patterns -> Argument Inspection.
        """
        # Exempt Core Tools from Security Checks
        if action_id.startswith("elemm:") or action_id in ["connect_to_site", "get_manifest", "get_landmarks", "inspect_landmark", "list_aliases", "clear_session"]:
            return {"allowed": True}

        action_lower = action_id.lower()
        short_action = action_id.split(":", 1)[1].lower() if ":" in action_id else action_lower
        segments = [s.lower() for s in action_id.replace("_", ":").split(":")]

        # --- A. WHITELIST CHECK (Zero Trust Mode) ---
        if self.enforce_whitelist:
            is_whitelisted = False
            if action_lower in self.allowed_actions or short_action in self.allowed_actions:
                is_whitelisted = True
            else:
                for segment in segments:
                    if segment in self.allowed_landmarks:
                        is_whitelisted = True
                        break
            
            if not is_whitelisted:
                return {
                    "allowed": False,
                    "reason": f"Access Denied: Action '{action_id}' is not in the whitelist.",
                    "remedy": self._get_remedy("whitelist_violation", "This gateway is in Zero-Trust mode. Only explicitly authorized tools can be used.")
                }

        # --- B. METHOD CHECK ---
        if method and self.allowed_methods:
            method_upper = method.upper()
            if method_upper not in self.allowed_methods:
                return {
                    "allowed": False,
                    "reason": f"HTTP method '{method_upper}' is restricted by security policy.",
                    "remedy": self._get_remedy("method_violation", f"Only the following methods are permitted: {', '.join(self.allowed_methods)}")
                }

        # --- C. BLACKLIST CHECK (Actions & Landmarks) ---
        if action_lower in self.disallowed_actions or short_action in self.disallowed_actions:
            return {
                "allowed": False,
                "reason": f"Action '{action_id}' is explicitly blacklisted.",
                "remedy": self._get_remedy(action_id, "Access to this specific endpoint is disabled for security reasons.")
            }

        for segment in segments:
            if segment in self.disallowed_landmarks:
                return {
                    "allowed": False,
                    "reason": f"Landmark area '{segment}' within path is restricted.",
                    "remedy": self._get_remedy(segment, f"Access to the '{segment}' functional area is disabled.")
                }

        # --- D. PATTERN & ARGUMENT CHECK ---
        # 1. Check Action ID against Patterns
        for p in self.patterns:
            matched = False
            if p["type"] == "regex":
                if p["val"].search(action_id): matched = True
            else:
                if p["val"] in action_lower: matched = True
            
            if matched:
                return {
                    "allowed": False,
                    "reason": f"Action contains restricted pattern '{p['raw']}'.",
                    "remedy": self._get_remedy(p["raw"], "This operation matches a restricted security pattern.")
                }

        # 2. Deep Argument Inspection (Recursive)
        if arguments:
            violation = self._check_value_recursive(arguments)
            if violation:
                return {
                    "allowed": False,
                    "reason": f"Argument value contains restricted pattern '{violation}'.",
                    "remedy": self._get_remedy(violation, "Input validation failed: One of the provided arguments contains restricted content.")
                }

        return {"allowed": True}

    def _check_value_recursive(self, val: Any) -> Optional[str]:
        """Deeply inspects a value (dict, list, string) for restricted patterns."""
        if isinstance(val, str):
            val_lower = val.lower()
            for p in self.patterns:
                if p["type"] == "regex":
                    if p["val"].search(val): return p["raw"]
                else:
                    if p["val"] in val_lower: return p["raw"]
        elif isinstance(val, dict):
            for k, v in val.items():
                res_k = self._check_value_recursive(k)
                if res_k: return res_k
                res_v = self._check_value_recursive(v)
                if res_v: return res_v
        elif isinstance(val, list):
            for item in val:
                res = self._check_value_recursive(item)
                if res: return res
        return None
