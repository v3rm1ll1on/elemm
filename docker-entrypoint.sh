#!/bin/sh
set -e

# Start the Elemm MCP SSE Gateway in the background
echo "Starting Elemm MCP SSE Gateway on port 8000..."
elemm-gateway --transport sse --host 0.0.0.0 --port 8000 &

# Start the Elemm Dashboard in the foreground
echo "Starting Elemm Dashboard on port 8090..."
exec elemm-dashboard --host 0.0.0.0 --port 8090
