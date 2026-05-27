# Copyright (C) 2026 Marc Stöcker
# Website: https://elemm.dev
#
# This program is licensed under the Business Source License 1.1 (BSL 1.1).
# See the LICENSE file in the root directory for details.

import os
import re
import importlib.metadata

def get_version() -> str:
    # 1. Try parsing pyproject.toml in development environment
    try:
        # Locate pyproject.toml relative to this file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Climb up to find pyproject.toml
        for _ in range(4):
            pyproject_path = os.path.join(current_dir, "pyproject.toml")
            if os.path.exists(pyproject_path):
                with open(pyproject_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    # Find version = "..." under [project]
                    match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
                    if match:
                        return match.group(1)
            parent = os.path.dirname(current_dir)
            if parent == current_dir:
                break
            current_dir = parent
    except Exception:
        pass

    # 2. Try metadata (installed production environment)
    try:
        return importlib.metadata.version("elemm")
    except importlib.metadata.PackageNotFoundError:
        pass
        
    # 3. Fallback
    return "1.2.0"

__version__ = get_version()
