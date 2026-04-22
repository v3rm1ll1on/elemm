from .base import BaseAIProtocolManager
from .fastapi import FastAPIProtocolManager, Elemm
from .models import AIAction, ActionParam
from .gateway import ElemmGateway

# Alias for backward compatibility
AIProtocolManager = FastAPIProtocolManager

__version__ = "0.4.1"
__all__ = ["Elemm", "ElemmGateway", "AIProtocolManager", "FastAPIProtocolManager", "BaseAIProtocolManager", "AIAction", "ActionParam"]
