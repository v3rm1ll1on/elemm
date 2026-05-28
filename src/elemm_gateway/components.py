# Copyright (C) 2026 Marc Stöcker
# Website: https://elemm.dev
#
# This program is licensed under the Business Source License 1.1 (BSL 1.1).
# See the LICENSE file in the root directory for details.

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