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

"""
🚀 ELEMM MINIMALIST ENTRY POINT
===============================

This script is the easiest way to connect an Elemm-compliant site to your AI agent.
Just copy the following JSON into your Claude Desktop config (usually at %APPDATA%/Claude/claude_desktop_config.json):

{
  "mcpServers": {
    "elemm": {
      "command": "python3",
      "args": ["/ABSOLUTE/PATH/TO/examples/mcp.py", "http://localhost:8000"],
      "env": {
        "PYTHONPATH": "/ABSOLUTE/PATH/TO/src"
      }
    }
  }
}

REPLACE "/ABSOLUTE/PATH/TO/" with your actual project path.
"""

import sys
import asyncio
import os

# Add src to sys.path automatically if run from the examples dir
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

try:
    from elemm_gateway.cli import async_main
except ImportError:
    print(f"Error: 'elemm' package not found at {src_path}. Please run 'pip install elemm' or check your paths.", file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    asyncio.run(async_main())
