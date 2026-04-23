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

from typing import Optional

class ElemmError(Exception):
    """Base exception for all elemm protocol errors."""
    pass

class ActionError(ElemmError):
    """Raised when a protocol action fails, supporting dynamic remedies."""
    def __init__(self, message: str, remedy: Optional[str] = None, instruction: Optional[str] = None, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.remedy = remedy
        self.instruction = instruction
        self.status_code = status_code

class LandmarkRegistrationError(ElemmError):
    """Raised when a landmark cannot be registered properly."""
    pass

class ManifestGenerationError(ElemmError):
    """Raised when the manifest cannot be generated."""
    pass

class LandmarkNotFoundError(ElemmError):
    """Raised when a requested landmark or group is not found."""
    pass
