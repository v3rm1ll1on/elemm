import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))
sys.path.append(str(Path(__file__).parent))

from api_elemm_v2 import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_manifest():
    response = client.get("/elemm/manifest")
    from elemm_v2.core.presenter import ManifestPresenter
    from api_elemm_v2 import manager
    manifest_obj = manager.get_manifest_object()
    presenter = ManifestPresenter()
    print("--- V2 RICH MANIFEST ---")
    print(presenter.to_markdown(manifest_obj))
    assert response.status_code == 200
    assert "landmarks" in response.json()
    print("\nSUCCESS: Manifest generated from YAML + Code binding!")

if __name__ == "__main__":
    test_manifest()
