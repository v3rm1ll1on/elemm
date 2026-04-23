# This file is part of Elemm.
#
# Elemm is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Elemm is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Elemm.  If not, see <https://www.gnu.org/licenses/>.

from contextvars import ContextVar
from typing import Dict

# Navigation context (current landmark)
landmark_ctx: ContextVar[str] = ContextVar("landmark_ctx", default="root")

# Session management (auth headers for different hosts)
session_headers: ContextVar[Dict[str, Dict[str, str]]] = ContextVar("session_headers", default={})
