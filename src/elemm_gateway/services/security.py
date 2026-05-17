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
            arg_check = self.are_arguments_allowed(arguments)
            if not arg_check["allowed"]:
                violation = arg_check["reason"].split("'")[1] if "'" in arg_check["reason"] else ""
                return {
                    "allowed": False,
                    "reason": arg_check["reason"],
                    "remedy": self._get_remedy(violation, "Input validation failed: One of the provided arguments contains restricted content.")
                }

        return {"allowed": True}

    def are_arguments_allowed(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Validates a dictionary of arguments against the security policy."""
        if not arguments:
            return {"allowed": True}
        violation = self._check_value_recursive(arguments)
        if violation:
            return {
                "allowed": False,
                "reason": f"Argument value contains restricted pattern '{violation}'."
            }
        return {"allowed": True}

    def is_query_allowed(self, query: str) -> Dict[str, Any]:
        """
        Validates a search query against the security policy,
        protecting against regex-injections and obfuscation.
        """
        if not query:
            return {"allowed": True}
            
        blocked_terms = []
        for p in self.patterns:
            blocked_terms.append(p["raw"][3:] if p["raw"].startswith("re:") else p["raw"])
        blocked_terms.extend(self.disallowed_landmarks)
        blocked_terms.extend(self.disallowed_actions)
        
        branches = query.split("|")
        for branch in branches:
            branch_clean = branch.strip()
            if not branch_clean:
                continue
            cleaned = branch_clean.replace(".*", "").replace(".+", "").replace("*", "").replace("?", "")
            if not cleaned:
                continue
                
            try:
                branch_pat = re.compile(cleaned, re.IGNORECASE)
            except re.error:
                branch_pat = re.compile(re.escape(cleaned), re.IGNORECASE)
                
            for term in blocked_terms:
                if branch_pat.search(term):
                    return {
                        "allowed": False,
                        "reason": f"Search query targets restricted pattern/area '{term}'."
                    }
        return {"allowed": True}

    def is_pattern_blocked(self, value: str) -> bool:
        """Helper to check if a string matches any disallowed pattern."""
        if not value:
            return False
        return self._check_value_recursive(value) is not None

    def validate_tool_call(self, tool_name: str, arguments: Dict[str, Any], method: Optional[str] = None) -> Dict[str, Any]:
        """
        Zentrales Sicherheits-Gate für alle Tool-Aufrufe.
        Prüft:
        1. Globale Argumenten-Muster (Hygiene- & Parameter-Schutz für alle Parameter)
        2. Werkzeug-spezifische Regeln (inspect_landmark, search_landmarks, call_action, direkte Aktionen)
        Gibt ein einheitliches Dict zurück: {"allowed": True} oder {"allowed": False, "reason": "...", "remedy": "..."}
        """
        if not arguments:
            arguments = {}

        # 1. Globaler Argumentenschutz (Deep Argument Inspection)
        arg_check = self.are_arguments_allowed(arguments)
        if not arg_check["allowed"]:
            violation = arg_check["reason"].split("'")[1] if "'" in arg_check["reason"] else ""
            return {
                "allowed": False,
                "reason": arg_check["reason"],
                "remedy": self._get_remedy(violation, "Input validation failed: One of the provided arguments contains restricted content.")
            }

        # 2. Werkzeug-spezifische Validierung
        if tool_name in ["inspect_landmark", "get_manifest"]:
            lm_id = arguments.get("landmark_id")
            if lm_id:
                ids = [lm_id] if isinstance(lm_id, str) else lm_id
                for tid in ids:
                    check = self.is_action_allowed(tid)
                    if not check["allowed"]:
                        return {
                            "allowed": False,
                            "reason": f"Access to '{tid}' is restricted.",
                            "remedy": check.get("remedy")
                        }

        elif tool_name == "search_landmarks":
            query = arguments.get("query")
            if query:
                check = self.is_query_allowed(query)
                if not check["allowed"]:
                    return check

        elif tool_name == "call_action":
            action = arguments.get("action")
            params = arguments.get("parameters", {})
            if action:
                check = self.is_action_allowed(action, method=method, arguments=params)
                if not check["allowed"]:
                    return check

        elif tool_name not in ["connect_to_site", "list_aliases", "clear_session", "get_landmarks"]:
            # Direkter API-Aufruf (nicht-Core Tools)
            check = self.is_action_allowed(tool_name, method=method, arguments=arguments)
            if not check["allowed"]:
                return check

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
