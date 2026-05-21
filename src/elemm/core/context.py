# Copyright (C) 2026 Marc Stöcker
# Website: https://elemm.dev
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

from contextvars import ContextVar
from typing import Dict, Optional, Any

# Trackt das aktuelle Landmark (Namespace) während der Ausführung
landmark_ctx: ContextVar[str] = ContextVar("landmark_ctx", default="root")

# Ermöglicht das Speichern von Session-Daten (z.B. Auth-Tokens) pro Ziel-System
session_ctx: ContextVar[Dict[str, Any]] = ContextVar("session_ctx", default={})

from typing import Any
