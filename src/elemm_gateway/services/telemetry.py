# Copyright (C) 2026 Marc Stöcker
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

import json
import logging
from typing import Any, Dict

logger = logging.getLogger("elemm-gateway")

class MonitoredReadStream:
    """Passively monitors the incoming MCP JSON-RPC stream for telemetry."""
    def __init__(self, stream, monitor, session_id, pending_map: Dict):
        self._stream = stream
        self._monitor = monitor
        self._session_id = session_id
        self._pending_map = pending_map

    async def receive(self):
        message = await self._stream.receive()
        try:
            # message is SessionMessage
            from mcp.shared.message import SessionMessage
            if isinstance(message, SessionMessage):
                rpc_msg = message.message
                # Extract data from Pydantic model
                data = rpc_msg.model_dump()
                method = data.get("method", "unknown")
                
                if method == "tools/call":
                    tool_name = data.get("params", {}).get("name")
                else:
                    tool_name = method

                msg_id = data.get("id")
                if msg_id is not None:
                    self._pending_map[msg_id] = tool_name
                
                self._monitor.report_activity(
                    last_action=f"WIRE IN: {tool_name}",
                    input_data=data,
                    chars_in=len(str(data)),
                    tokens_in=self._monitor.estimate_tokens(data, is_input=True),
                    status="pending",
                    session_id=self._session_id
                )
        except Exception as e:
            logger.debug(f"Telemetry: Failed to parse incoming message: {e}")
        return message

    async def aclose(self):
        await self._stream.aclose()

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return await self.receive()
        except Exception: # Handle EOF/Closed stream
            raise StopAsyncIteration

class MonitoredWriteStream:
    """Passively monitors the outgoing MCP JSON-RPC stream for telemetry."""
    def __init__(self, stream, monitor, session_id, pending_map: Dict):
        self._stream = stream
        self._monitor = monitor
        self._session_id = session_id
        self._pending_map = pending_map

    async def send(self, message):
        try:
            from mcp.shared.message import SessionMessage
            if isinstance(message, SessionMessage):
                rpc_msg = message.message
                data = rpc_msg.model_dump()
                msg_id = data.get("id")
                tool_name = self._pending_map.pop(msg_id, "result") if msg_id is not None else "event"
                
                self._monitor.report_activity(
                    last_action=f"WIRE OUT: {tool_name}",
                    output_data=data,
                    chars_out=len(str(data)),
                    tokens_out=self._monitor.estimate_tokens(data, is_input=False),
                    status="success" if "error" not in data else "error",
                    session_id=self._session_id
                )
        except Exception as e:
            logger.debug(f"Telemetry: Failed to parse outgoing message: {e}")
        await self._stream.send(message)

    async def aclose(self):
        await self._stream.aclose()
