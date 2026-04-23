# This file is part of Elemm.
#
# Elemm is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Elemm is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Elemm.  If not, see <https://www.gnu.org/licenses/>.

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

    args = parser.parse_args()

    # Configure logging to STDERR strictly
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
        force=True # Ensure we override any previous config
    )
    
    logger = logging.getLogger("elemm-cli")

    try:
        gateway = ElemmGateway(server_name=args.name)
        
        if args.url:
            logger.info(f"Auto-connecting to: {args.url}")
            await gateway._connect(args.url)
            
        # Log available tools for debugging (to stderr)
        available_tools = await gateway._handle_list_tools()
        tool_names = ", ".join([t.name for t in available_tools])
        logger.info(f"Elemm Gateway started. Available tools: {tool_names}")
        
        # Run the server
        from mcp.server.stdio import stdio_server
        async with stdio_server() as (read, write):
            await gateway.server.run(
                read, 
                write, 
                gateway.server.create_initialization_options()
            )
            
    except KeyboardInterrupt:
        logger.info("Gateway stopped by user.")
    except Exception as e:
        logger.error(f"Gateway failed: {e}")
        sys.exit(1)

def main():
    asyncio.run(async_main())

if __name__ == "__main__":
    main()
