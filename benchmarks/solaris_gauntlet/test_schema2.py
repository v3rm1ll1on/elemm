import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/../../")
from benchmarks.solaris_gauntlet.api_elemm import app, ai

action = ai.get_action("quarantine_principal")
print("Parameters:", action.parameters)
print("Payload:", action.payload)
for p in action.payload:
    print(p.name, p.required)
