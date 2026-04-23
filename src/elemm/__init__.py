from .core.manager import BaseAIProtocolManager
from .integrations.fastapi.manager import FastAPIProtocolManager, Elemm
from .core.models import AIAction, ActionParam

# Alias for backward compatibility
AIProtocolManager = FastAPIProtocolManager

__version__ = "0.8.1"
__all__ = ["Elemm", "AIProtocolManager", "FastAPIProtocolManager", "BaseAIProtocolManager", "AIAction", "ActionParam"]
