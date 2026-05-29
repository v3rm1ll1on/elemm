# Copyright (C) 2026 Marc Stöcker
# Website: https://elemm.dev
#
# This program is licensed under the Business Source License 1.1 (BSL 1.1).
# See the LICENSE file in the root directory for details.

import sys
import argparse
import logging
import asyncio
from elemm_gateway.server import ElemmGateway

async def async_main():
    parser = argparse.ArgumentParser(description="Elemm Gateway: Connect ANY website to your AI agent.")
    parser.add_argument("url", nargs="?", help="Optional: Initial URL to connect to at startup")
    parser.add_argument("--name", default="elemm-gateway", help="Custom name for the MCP server")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio", help="Transport mechanism (default: stdio)")
    parser.add_argument("--host", default="0.0.0.0", help="Host for SSE server")
    parser.add_argument("--port", type=int, default=8000, help="Port for SSE server")
    parser.add_argument("--bridge", help="SSE server URL to bridge to (runs in stdio <-> SSE proxy mode)")
    parser.add_argument("--session-id", default=None, help="Session ID for the gateway instance (defaults to --name)")

    args = parser.parse_args()

    if args.url == "cfg-gen":
        from elemm_gateway.config_gen import run_config_generator
        run_config_generator()
        sys.exit(0)

    # Configure logging to STDERR strictly (essential for STDIO transport)
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
        force=True
    )
    
    logger = logging.getLogger("elemm-cli")

    # If running in bridge mode, intercept execution and run the stdio <-> SSE proxy
    if args.bridge:
        logger.info(f"Running in Bridge Mode. Tunneling stdio <-> {args.bridge}")
        from mcp.client.sse import sse_client
        from mcp.server.stdio import stdio_server
        from mcp.shared.message import SessionMessage
        import httpx
        
        try:
            async with stdio_server() as (stdio_read, stdio_write):
                stdin_queue = asyncio.Queue()
                
                async def read_stdin():
                    try:
                        async for session_message in stdio_read:
                            if isinstance(session_message, Exception):
                                logger.error(f"Error reading from stdin: {session_message}")
                                continue
                            await stdin_queue.put(session_message)
                    except Exception as e:
                        logger.error(f"Stdin reader stopped: {e}")
                    finally:
                        logger.info("Stdin reader finished. Stopping bridge.")

                async def sse_worker():
                    while True:
                        try:
                            from urllib.parse import urlencode
                            params = urlencode({"session_id": args.name})
                            bridge_url = f"{args.bridge}?{params}" if "?" not in args.bridge else f"{args.bridge}&{params}"
                            
                            logger.info(f"Connecting to SSE server at {bridge_url}...")
                            async with sse_client(bridge_url) as (sse_read, sse_write):
                                logger.info("SSE connection established. Tunnel active.")
                                
                                async def forward_stdin():
                                    while True:
                                        msg = await stdin_queue.get()
                                        try:
                                            await sse_write.send(msg)
                                        except Exception as e:
                                            logger.error(f"Failed to forward message to SSE: {e}")
                                            # Put it back to retry
                                            await stdin_queue.put(msg)
                                            raise e
                                        finally:
                                            stdin_queue.task_done()

                                async def forward_sse():
                                    async for msg in sse_read:
                                        await stdio_write.send(msg)

                                forward_stdin_task = asyncio.create_task(forward_stdin())
                                forward_sse_task = asyncio.create_task(forward_sse())
                                
                                try:
                                    done, pending = await asyncio.wait(
                                        [forward_stdin_task, forward_sse_task],
                                        return_when=asyncio.FIRST_COMPLETED
                                    )
                                    for task in done:
                                        task.result()
                                finally:
                                    for task in [forward_stdin_task, forward_sse_task]:
                                        if not task.done():
                                            task.cancel()
                                            try:
                                                await task
                                            except asyncio.CancelledError:
                                                pass
                        except (httpx.HTTPError, Exception) as e:
                            logger.error(f"SSE connection lost or failed: {e}. Retrying in 2 seconds...")
                            await asyncio.sleep(2)
                
                stdin_task = asyncio.create_task(read_stdin())
                sse_task = asyncio.create_task(sse_worker())
                
                try:
                    done, pending = await asyncio.wait(
                        [stdin_task, sse_task],
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    for task in done:
                        task.result()
                finally:
                    for task in [stdin_task, sse_task]:
                        if not task.done():
                            task.cancel()
                            try:
                                await task
                            except asyncio.CancelledError:
                                pass
            return
        except Exception as e:
            logger.error(f"Bridge mode fatal error: {e}")
            sys.exit(1)

    try:
        session_id = args.session_id if args.session_id else args.name
        gateway = ElemmGateway(session_id=session_id, server_name=args.name)
        
        # Banner removed for protocol purity

        if args.url:
            logger.info(f"Auto-connecting to: {args.url}")
            await gateway._connect(args.url)
        else:
            pass
            
        if args.transport == "stdio":
            logger.info("Transport: STDIO (Perfect for Claude Desktop / Cursor)")
            await gateway.run()
        else:
            logger.info(f"Transport: SSE (Webserver Mode)")
            logger.info(f"Listening on: http://{args.host}:{args.port}/sse")
            from starlette.applications import Starlette
            from starlette.routing import Route, Mount
            from mcp.server.sse import SseServerTransport
            import uvicorn

            sse = SseServerTransport("/messages")
            active_sessions = set()

            async def handle_sse(request):
                from elemm_gateway.services.connected_clients import current_client_id
                from elemm_gateway.services.monitor import get_monitor
                import uuid
                
                sid = request.query_params.get("session_id", "default")
                
                # Check for collision and assign a unique suffix if already active
                if sid in active_sessions:
                    original_sid = sid
                    sid = f"{sid}-{str(uuid.uuid4())[:8]}"
                    logger.warning(f"Session ID collision detected for '{original_sid}'. Assigned unique ID: '{sid}'")
                
                active_sessions.add(sid)
                
                # Register session in dashboard immediately upon connection
                get_monitor().report_activity(
                    last_action=f"Client connected: {sid}",
                    status="success",
                    session_id=sid
                )
                
                token = current_client_id.set(sid)
                try:
                    async with sse.connect_sse(request.scope, request.receive, request._send) as (read, write):
                        await gateway.server.run(
                            read,
                            write,
                            gateway.server.create_initialization_options()
                        )
                finally:
                    active_sessions.discard(sid)
                    get_monitor().report_activity(
                        last_action=f"Client disconnected: {sid}",
                        status="success",
                        session_id=sid
                    )
                    current_client_id.reset(token)
                from starlette.responses import Response
                return Response()

            from starlette.middleware import Middleware
            from starlette.middleware.cors import CORSMiddleware

            app = Starlette(
                debug=True,
                routes=[
                    Route("/sse", endpoint=handle_sse),
                    Mount("/messages", app=sse.handle_post_message),
                ],
                middleware=[
                    Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
                ]
            )

            config = uvicorn.Config(app, host=args.host, port=args.port, log_level="info")
            server = uvicorn.Server(config)
            await server.serve()
            
    except KeyboardInterrupt:
        logger.info("Gateway stopped by user.")
    except Exception as e:
        logger.error(f"Gateway failed: {e}")
        sys.exit(1)

def main():
    asyncio.run(async_main())

if __name__ == "__main__":
    main()