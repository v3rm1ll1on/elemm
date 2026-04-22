import sys
import argparse
import logging
from .gateway import ElemmGateway

def main():
    parser = argparse.ArgumentParser(description="Elemm Gateway: Connect ANY website to your AI agent.")
    parser.add_argument("url", help="The URL of the Elemm-compliant website (e.g., https://solaris-hub.ai)")
    parser.add_argument("--name", help="Custom name for the MCP server")
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
        gateway = ElemmGateway(target_url=args.url, server_name=args.name)
        logging.info(f"Connecting to Elemm site: {args.url}")
        gateway.run()
    except KeyboardInterrupt:
        logging.info("Gateway stopped by user.")
        sys.exit(0)
    except Exception as e:
        logging.error(f"Gateway failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
