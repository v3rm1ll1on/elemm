import pytest
from fastapi import FastAPI
from elemm.core.manager import AIProtocolManager
from elemm.gateways.fastapi import FastAPIGateway
from starlette.testclient import TestClient

def test_fastapi_tag_namespace_bridge():
    """
    Testet, ob FastAPI-Tags automatisch als Namespaces für native Landmarks übernommen werden.
    """
    manager = AIProtocolManager()
    gateway = FastAPIGateway(manager)
    app = FastAPI()

    # 1. Registriere ein Tool ohne Namespace
    @app.get("/test", tags=["Group1"])
    @manager.landmark("my_native_tool")
    def test_tool():
        return "ok"

    # 2. Binde die App an den Gateway (hier passiert die Magie)
    gateway.bind_to_app(app)

    # 3. Prüfe, ob die ID im Manager korrigiert wurde
    # Erwartet: "Group1:test_tool" statt "my_native_tool:test_tool"
    assert "Group1:test_tool" in manager.landmarks
    assert "my_native_tool" not in manager.landmarks
    
    # 4. Prüfe das Manifest via JSON (mit full=true um Hierarchie zu sehen)
    client = TestClient(app)
    resp = client.get("/.well-known/elemm-manifest.md?format=json&full=true")
    data = resp.json()
    
    landmark_ids = [l["id"] for l in data["landmarks"]]
    print(f"DEBUG IDs: {landmark_ids}")
    assert "Group1:test_tool" in landmark_ids
    
    # Prüfe, ob die Area "Group1" auch erstellt wurde (is_tool muss False sein)
    assert any(l["id"] == "Group1" and l["is_tool"] == False for l in data["landmarks"])

if __name__ == "__main__":
    pytest.main([__file__])
