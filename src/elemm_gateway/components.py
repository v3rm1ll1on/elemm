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

"""
Elemm Gateway Components (Facade)
This file re-exports services for backward compatibility.
The actual logic has been moved to the services/ directory.
"""

from .services.manifest import ManifestBuilder
from .services.config import ConfigManager
from .services.security import SecurityPolicy
from .services.vault import VaultManager
from .services.hygiene import ResponseSquisher
from .services.executors import GraphQLExecutor, OpenAPIExecutor
from .services.sequencer import SequenceEngine

__all__ = [
    "ManifestBuilder",
    "ConfigManager",
    "SecurityPolicy",
    "VaultManager",
    "ResponseSquisher",
    "GraphQLExecutor",
    "OpenAPIExecutor",
    "SequenceEngine",
]
