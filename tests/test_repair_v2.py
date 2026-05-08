import pytest
from elemm.core.manager import AIProtocolManager
from elemm.core.models import Parameter

@pytest.mark.asyncio
async def test_dynamic_remedy_from_landmark():
    manager = AIProtocolManager(instructions="Test")
    
    # Landmark mit spezifischem Tipp
    manager.landmark(
        "auth:login",
        parameters=[Parameter(name="user", description="Username")],
        remedy="Get your username from the HR terminal first."
    )(lambda user: {"ok": True})
    
    # Aufruf OHNE den erforderlichen Parameter 'user'
    res = await manager.call_action("auth:login", {})
    
    assert res["status"] == "error"
    # Der spezifische Tipp aus der Landmark muss in 'remedy' stehen
    assert res["remedy"] == "Get your username from the HR terminal first."
