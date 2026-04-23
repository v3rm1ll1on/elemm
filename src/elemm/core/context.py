from contextvars import ContextVar
from typing import Dict

# Navigation context (current landmark)
landmark_ctx: ContextVar[str] = ContextVar("landmark_ctx", default="root")

# Session management (auth headers for different hosts)
session_headers: ContextVar[Dict[str, Dict[str, str]]] = ContextVar("session_headers", default={})
