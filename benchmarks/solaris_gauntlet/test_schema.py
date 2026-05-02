import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from api_elemm import app
route = next(r for r in app.routes if r.path == "/ops/quarantine")
print(route.body_field.field_info.annotation.model_json_schema())
