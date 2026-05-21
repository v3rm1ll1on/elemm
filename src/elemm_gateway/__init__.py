# Copyright (C) 2026 Marc Stöcker
# Website: https://elemm.dev
#
# This file is part of Elemm.
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
