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
