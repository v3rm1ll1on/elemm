class ElemmError(Exception):
    """Base exception for all elemm protocol errors."""
    pass

class LandmarkRegistrationError(ElemmError):
    """Raised when a landmark cannot be registered properly."""
    pass

class ManifestGenerationError(ElemmError):
    """Raised when the manifest cannot be generated."""
    pass

class LandmarkNotFoundError(ElemmError):
    """Raised when a requested landmark or group is not found."""
    pass
