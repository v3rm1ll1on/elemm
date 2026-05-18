# Copyright (C) 2026 Marc Stöcker
# Part of Elemm v1.2.0 - Connected Clients Service Module

from contextvars import ContextVar

# Asynchroner, Task-lokaler Speicher für die ID des aktuell verbundenen Clients
current_client_id: ContextVar[str] = ContextVar("current_client_id", default="default")
