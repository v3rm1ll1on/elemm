import pytest
from elemm_v2.core.manager import AIProtocolManager
from elemm_v2.core.models import LandmarkRegistry, LandmarkMetadata, Parameter

class MockRegistry(LandmarkRegistry):
    def get(self, landmark_id: str):
        if landmark_id == "noc:resolve_ip_to_host":
            return LandmarkMetadata(
                description="Test Tool",
                parameters=[Parameter(name="ip", description="Target IP", required=True)]
            )
        return None

@pytest.mark.asyncio
async def test_missing_parameter_validation():
    registry = MockRegistry()
    manager = AIProtocolManager(registry=registry)
    
    @manager.bind("noc:resolve_ip_to_host")
    async def mock_handler(ip: str):
        return {"hostname": "srv-test"}
        
    # Aufruf ohne Parameter
    result = await manager.call_action("noc:resolve_ip_to_host", {})
    
    assert "status" in result
    assert result["status"] == "error"
    assert "Missing required parameters" in result["message"]
    assert "ip" in result["message"]

@pytest.mark.asyncio
async def test_valid_parameter_call():
    registry = MockRegistry()
    manager = AIProtocolManager(registry=registry)
    
    @manager.bind("noc:resolve_ip_to_host")
    async def mock_handler(ip: str):
        return {"hostname": f"srv-{ip}"}
        
    # Aufruf mit Parameter
    result = await manager.call_action("noc:resolve_ip_to_host", {"ip": "10.0.0.1"})
    
    assert result == {"hostname": "srv-10.0.0.1"}

@pytest.mark.asyncio
async def test_smart_unboxing_in_sequencer():
    registry = MockRegistry()
    manager = AIProtocolManager(registry=registry)
    from elemm_v2.core.sequencer import SequenceEngine
    sequencer = SequenceEngine(manager)
    
    context = {"test_alias": {"ip": "192.168.1.1"}}
    # Simulate piping where the parameter name matches the dict key
    params = {"ip": "$test_alias"}
    
    # We test the private method directly for simplicity
    resolved, err = sequencer._resolve_piping(params["ip"], context)
    
    # We expect the dictionary to be resolved, then the sequencer run loop processes it...
    # Wait, _resolve_piping returns the raw context value. The unboxing happens AFTER.
    # Let's test the dictionary resolution logic directly.
    data = {"ip": "$test_alias"}
    resolved_dict, err = sequencer._resolve_piping(data, context)
    
    assert err is None
    assert resolved_dict["ip"] == "192.168.1.1"

