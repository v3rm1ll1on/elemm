# Copyright (C) 2026 Marc Stöcker
# Website: https://elemm.dev
#
# This program is licensed under the Business Source License 1.1 (BSL 1.1).
# See the LICENSE file in the root directory for details.

"""
Elemm Gateway Hygiene
Re-exports the ResponseSquisher from elemm.core.hygiene for backward compatibility.
"""

from elemm.core.hygiene import ResponseSquisher

__all__ = ["ResponseSquisher"]