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

    args = parser.parse_args()

    # Configure logging to STDERR strictly (essential for STDIO transport)
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
        force=True
    )
    
    logger = logging.getLogger("elemm-cli")

    try:
        gateway = ElemmGateway(server_name=args.name)
        
        # Friendly greeting on stderr
        banner = f"""
╔════════════════════════════════════════════════════════════════════╗
║  🚀 ELEMM GATEWAY v1.1 - Active & Ready                            ║
║  Connect ANY website or OpenAPI spec to your AI Agent.             ║
╚════════════════════════════════════════════════════════════════════╝
"""
        print(banner, file=sys.stderr)

        if args.url:
            logger.info(f"Auto-connecting to: {args.url}")
            await gateway._connect(args.url)
        else:
            logger.info("No initial URL provided. Waiting for agent to call 'connect_to_site'.")
            print("💡 TIP: Tell your Agent: 'Connect to http://example.com' or provide an OpenAPI URL.", file=sys.stderr)
            
        if args.transport == "stdio":
            logger.info("Transport: STDIO (Perfect for Claude Desktop / Cursor)")
            from mcp.server.stdio import stdio_server
            async with stdio_server() as (read, write):
                await gateway.server.run(
                    read, 
                    write, 
                    gateway.server.create_initialization_options()
                )
        else:
            logger.info(f"Transport: SSE (Webserver Mode)")
            logger.info(f"Listening on: http://{args.host}:{args.port}/sse")
            from starlette.applications import Starlette
            from starlette.routing import Route
            from mcp.server.sse import SseServerTransport
            import uvicorn

            sse = SseServerTransport("/messages")
            # ... rest of the sse logic (I will keep it as is from previous edit)

            async def handle_sse(request):
                async with sse.connect_sse(request.scope, request.receive, request._send) as (read, write):
                    await gateway.server.run(
                        read,
                        write,
                        gateway.server.create_initialization_options()
                    )

            async def handle_messages(request):
                await sse.handle_post_message(request.scope, request.receive, request._send)

            app = Starlette(
                debug=True,
                routes=[
                    Route("/sse", endpoint=handle_sse),
                    Route("/messages", endpoint=handle_messages, methods=["POST"]),
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
