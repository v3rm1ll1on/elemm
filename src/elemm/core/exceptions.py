# Copyright (C) 2026 Marc Stöcker
# Website: https://elemm.dev
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

from typing import Optional

class ElemmError(Exception):
    """Base class for all Elemm errors."""
    def __init__(
        self, 
        message: str, 
        remedy: Optional[str] = None, 
        instruction: Optional[str] = None,
        status_code: int = 400
    ):
        super().__init__(message)
        self.message = message
        self.remedy = remedy
        self.instruction = instruction
        self.status_code = status_code

    def to_dict(self) -> dict:
        res = {"status": "error", "message": self.message}
        if self.remedy: res["remedy"] = self.remedy
        if self.instruction: res["instruction"] = self.instruction
        return res

class ActionError(ElemmError):
    """Raised when an action (write operation) fails."""
    pass

class LandmarkNotFoundError(ElemmError):
    """Raised when a landmark ID is not found."""
    def __init__(self, landmark_id: str):
        super().__init__(
            message=f"Landmark '{landmark_id}' not found.",
            remedy="Check the manifest for available landmark IDs.",
            status_code=404
        )
