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

import pytest
import sys
import asyncio
from unittest.mock import AsyncMock, patch
from elemm_gateway.cli import async_main

@pytest.mark.asyncio
async def test_cli_bridge_mode_success():
    # Simulate: elemm-gateway --bridge http://localhost:8000/sse
    test_args = ["elemm-gateway", "--bridge", "http://localhost:8000/sse"]
    
    # Mock SSE streams
    mock_sse_read = AsyncMock()
    mock_sse_write = AsyncMock()
    
    # Simulate receiving an incoming JSON-RPC notification from the SSE stream
    from mcp.types import JSONRPCNotification
    from mcp.shared.message import SessionMessage
    mock_notification = JSONRPCNotification(jsonrpc="2.0", method="test_notification", params={})
    mock_session_notification = SessionMessage(mock_notification)
    
    async def mock_async_gen():
        yield mock_session_notification
        # yield once, then stop iteration to complete test execution
        await asyncio.sleep(0.01)
        
    mock_sse_read.__aiter__.side_effect = mock_async_gen
    
    # Mock Stdio streams using the official stdio_server format
    mock_stdio_read = AsyncMock()
    mock_stdio_write = AsyncMock()
    
    from mcp.types import JSONRPCRequest
    from mcp.shared.message import SessionMessage
    mock_request = JSONRPCRequest(jsonrpc="2.0", method="test_request", id=1)
    mock_session_msg = SessionMessage(mock_request)
    
    async def mock_stdio_gen():
        yield mock_session_msg
        await asyncio.sleep(0.01)
        
    mock_stdio_read.__aiter__.side_effect = mock_stdio_gen
    
    with patch("sys.argv", test_args), \
         patch("mcp.client.sse.sse_client") as mock_sse_client, \
         patch("mcp.server.stdio.stdio_server") as mock_stdio_server:
         
         # Yield our mocked read/write channels for SSE and Stdio
         mock_sse_client.return_value.__aenter__.return_value = (mock_sse_read, mock_sse_write)
         mock_stdio_server.return_value.__aenter__.return_value = (mock_stdio_read, mock_stdio_write)
         
         # Execute bridge main
         await async_main()
         
         # Assert 1: Correctly connected to the user's targeted SSE server
         mock_sse_client.assert_called_once_with("http://localhost:8000/sse")
         
         # Assert 2: Request from stdio forwarded to the SSE write channel
         mock_sse_write.send.assert_called_once_with(mock_session_msg)
         
         # Assert 3: Notification from SSE stream forwarded to stdio write channel
         mock_stdio_write.send.assert_called_once()
         sent_stdout_msg = mock_stdio_write.send.call_args[0][0]
         assert sent_stdout_msg.message.method == "test_notification"
