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

# By default, start both services (SSE gateway and dashboard) and propagate termination signals gracefully
gateway_pid=""
dashboard_pid=""

cleanup() {
    echo "Container stopping, terminating background processes gracefully..."
    if [ -n "$gateway_pid" ]; then
        kill -TERM "$gateway_pid" 2>/dev/null || true
    fi
    if [ -n "$dashboard_pid" ]; then
        kill -TERM "$dashboard_pid" 2>/dev/null || true
    fi
    wait "$gateway_pid" 2>/dev/null || true
    wait "$dashboard_pid" 2>/dev/null || true
    echo "Processes terminated cleanly."
    exit 0
}

trap cleanup INT TERM

echo "Starting Elemm MCP SSE Gateway on port 8000..."
elemm-gateway --transport sse --host 0.0.0.0 --port 8000 &
gateway_pid=$!

echo "Starting Elemm Dashboard on port 8090..."
elemm-dashboard --host 0.0.0.0 --port 8090 &
dashboard_pid=$!

# Wait on both processes so that this script (PID 1) continues running and receives signals
wait "$gateway_pid" "$dashboard_pid" 2>/dev/null || true
