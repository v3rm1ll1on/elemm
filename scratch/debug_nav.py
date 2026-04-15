import sys
sys.path.insert(0, "src") # Force local src
import elemm
print(f"DEBUG: elemm file location: {elemm.__file__}")

from fastapi import FastAPI
from elemm.fastapi import FastAPIProtocolManager

tags_metadata = [
    {"name": "SecretModule", "description": "Highly classified tools."}
]
app = FastAPI(openapi_tags=tags_metadata)
ai = FastAPIProtocolManager(agent_welcome="Welcome")

@ai.landmark(id="classified_tool", type="read", tags=["SecretModule"])
@app.get("/secret")
def secret(): return {}

@ai.landmark(id="global_tool", type="read")
@app.get("/global")
def glb(): return {}

ai.bind_to_app(app)

print("\n--- ROOT MANIFEST ---")
manifest = ai.get_manifest()
for a in manifest["actions"]:
    print(f"ID: {a['id']}, Groups: {a.get('groups')}")

print("\n--- SECRET MODULE MANIFEST ---")
manifest = ai.get_manifest(group="SecretModule")
for a in manifest["actions"]:
    print(f"ID: {a['id']}, Groups: {a.get('groups')}")
