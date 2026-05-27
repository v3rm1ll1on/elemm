# Copyright (C) 2026 Marc Stöcker
# Website: https://elemm.dev
#
# This program is licensed under the Business Source License 1.1 (BSL 1.1).
# See the LICENSE file in the root directory for details.

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