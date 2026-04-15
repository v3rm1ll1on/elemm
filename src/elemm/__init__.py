from .base import BaseAIProtocolManager
from .fastapi import FastAPIProtocolManager
from .models import AIAction, ActionParam

# Alias for backward compatibility and convenience
AIProtocolManager = FastAPIProtocolManager

__version__ = "0.3.1"
__all__ = ["AIProtocolManager", "FastAPIProtocolManager", "BaseAIProtocolManager", "AIAction", "ActionParam"]
