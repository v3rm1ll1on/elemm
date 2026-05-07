import pytest
from fastapi import FastAPI
from elemm_v2.core.manager import AIProtocolManager
from elemm_v2.core.models import Landmark

@pytest.mark.asyncio
async def test_manager_auto_flattening():
    # Test mit niedrigem Threshold
    manager = AIProtocolManager(instructions="Test", hybrid_threshold=2)
    
    @manager.bind("root_tool")
    def tool1(): pass
    
    @manager.bind("group:tool2")
    def tool2(): pass
    
    @manager.bind("group:tool3")
    def tool3(): pass

    # Wir haben 3 Tools, Threshold ist 2 -> Sollte NICHT flach sein (Hierarchisch)
    lms = manager.get_landmarks()
    ids = [l.id for l in lms]
    assert "root_tool" in ids
    assert "group:tool2" not in ids # Versteckt in Hierarchie
    
    # Jetzt Threshold erhöhen -> Sollte flach sein
    manager.hybrid_threshold = 10
    lms = manager.get_landmarks()
    ids = [l.id for l in lms]
    assert "root_tool" in ids
    assert "group:tool2" in ids # Sichtbar wegen Flattening

@pytest.mark.asyncio
async def test_manager_noise_detection():
    manager = AIProtocolManager(instructions="Test")
    
    @manager.bind("tool")
    def my_tool(a: int):
        return {"a": a}
    
    # Call mit Noise (Parameter 'b' existiert nicht)
    # Da wir in v2 Noise nur loggen oder in die Response packen (je nach Implementierung)
    # prüfen wir hier die Sanitization und das Logging-Verhalten (simuliert)
    res = await manager.call_action("tool", {"a": 1, "b": 2})
    assert res == {"a": 1} # 'b' wurde ignoriert (Sanitization)

@pytest.mark.asyncio
async def test_manager_404_remedy():
    manager = AIProtocolManager(instructions="Test")
    @manager.bind("known_tool")
    def tool(): pass
    
    res = await manager.call_action("unknown", {})
    assert res["status"] == "error"
    assert "Landmark 'unknown' not found" in res["message"]
    assert "remedy" in res
    assert "known_tool" in res["remedy"] # Schlägt existierende Tools vor
