#!/bin/sh
set -e

# If the first argument is "elemm-gateway" or starts with a dash "-", run the gateway directly (perfect for stdio)
if [ "$1" = "elemm-gateway" ] || [ "${1#-}" != "$1" ]; then
    # If it starts with a dash, prepend elemm-gateway
    if [ "${1#-}" != "$1" ]; then
        set -- elemm-gateway "$@"
    fi
    exec "$@"
fi

# Otherwise, if it's another specific command, run that
if [ "$1" = "elemm-dashboard" ]; then
    exec "$@"
fi

# By default, start both services (SSE gateway in the background, dashboard in the foreground)
echo "Starting Elemm MCP SSE Gateway on port 8000..."
elemm-gateway --transport sse --host 0.0.0.0 --port 8000 &

echo "Starting Elemm Dashboard on port 8090..."
exec elemm-dashboard --host 0.0.0.0 --port 8090
