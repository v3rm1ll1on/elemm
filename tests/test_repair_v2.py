import pytest
from elemm.core.repair import SmartRepairEngine

def test_repair_normalize_id():
    assert SmartRepairEngine.normalize_id("Get_Weather_Data!") == "getweatherdata"
    assert SmartRepairEngine.normalize_id(123) == "123"

def test_repair_missing_action():
    available = ["get_weather", "set_light"]
    
    # Normalized match suggestion
    res = SmartRepairEngine.handle_missing_action("GetWeather", available)
    assert "get_weather" in res.remedy
    assert res.suggested_fix == "get_weather"
    
    # Fuzzy match
    res = SmartRepairEngine.handle_missing_action("weather_info", available)
    assert "get_weather" in res.remedy

def test_repair_invalid_params():
    schema = {"city": "string", "days": "integer"}
    res = SmartRepairEngine.handle_invalid_params("weather", ["city"], schema)
    assert "city" in res.message
    assert "weather" in res.example
    assert res.expected_schema == schema

def test_repair_prohibited_direct_call():
    res = SmartRepairEngine.handle_prohibited_direct_call("tool", {"q": 1})
    assert "strictly prohibited" in res.message.lower()
    assert "call_action" in res.remedy

def test_repair_namespace_execution():
    res = SmartRepairEngine.handle_namespace_execution_attempt("home")
    assert "Landmark Namespace" in res.message
    assert "inspect_landmarks" in res.remedy

def test_repair_placeholder_detected():
    res = SmartRepairEngine.handle_placeholder_detected("city", "$prev_result.city")
    assert "unresolved variable" in res.message
    
    res = SmartRepairEngine.handle_placeholder_detected("city", "UNKNOWN")
    assert "placeholder value" in res.message

def test_repair_invalid_value_cases():
    allowed = ["Red", "Blue", "Green"]
    
    # Case mismatch fix
    res = SmartRepairEngine.handle_invalid_value("color", "red", allowed)
    assert res.suggested_fix == "Red"
    
    # Normalized match
    res = SmartRepairEngine.handle_invalid_value("color", "  b-l-u-e  ", allowed)
    assert res.suggested_fix == "Blue"
    
    # Fuzzy fallback
    res = SmartRepairEngine.handle_invalid_value("color", "Gree", allowed)
    assert res.suggested_fix == "Green"
