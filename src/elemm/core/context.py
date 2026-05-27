# Copyright (C) 2026 Marc Stöcker
# Website: https://elemm.dev
#
# This program is licensed under the Business Source License 1.1 (BSL 1.1).
# See the LICENSE file in the root directory for details.

from contextvars import ContextVar
from typing import Dict, Optional, Any

# Trackt das aktuelle Landmark (Namespace) während der Ausführung
landmark_ctx: ContextVar[str] = ContextVar("landmark_ctx", default="root")

# Ermöglicht das Speichern von Session-Daten (z.B. Auth-Tokens) pro Ziel-System
session_ctx: ContextVar[Dict[str, Any]] = ContextVar("session_ctx", default={})

from typing import Any