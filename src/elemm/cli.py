import sys
import argparse
import logging
import asyncio
from .gateway import ElemmGateway

def main():
    parser = argparse.ArgumentParser(description="Elemm Gateway: Connect ANY website to your AI agent.")
    parser.add_argument("url", nargs="?", help="Optional: Initial URL to connect to at startup")
    parser.add_argument("--name", default="elemm-gateway", help="Custom name for the MCP server")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr
    )

    try:
        gateway = ElemmGateway(server_name=args.name)
        if args.url:
            logging.info(f"Auto-connecting to: {args.url}")
            # We run the initial connect in the background or just set the target
            # For simplicity, we just trigger the initial logic if a URL is provided
            asyncio.run(gateway._connect(args.url))
            
        logging.info("Elemm Gateway started. Available tools: connect_to_site")
        gateway.run()
    except KeyboardInterrupt:
        logging.info("Gateway stopped by user.")
        sys.exit(0)
    except Exception as e:
        logging.error(f"Gateway failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
