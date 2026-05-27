# Copyright (C) 2026 Marc Stöcker
# Website: https://elemm.dev
#
# This program is licensed under the Business Source License 1.1 (BSL 1.1).
# See the LICENSE file in the root directory for details.

from contextvars import ContextVar

# Asynchroner, Task-lokaler Speicher für die ID des aktuell verbundenen Clients
current_client_id: ContextVar[str] = ContextVar("current_client_id", default="default")