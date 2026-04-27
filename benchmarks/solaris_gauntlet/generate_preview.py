import sys
import os

# Pfad zum Source-Verzeichnis hinzufügen
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from solaris_gauntlet.api_elemm import ai
from elemm.mcp.manifest import ManifestGenerator

# Manifest generieren
gen = ManifestGenerator(ai)
manifest_text = gen.generate_full()

# In Datei speichern
output_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "manifest_preview.md"))
with open(output_path, "w") as f:
    f.write(manifest_text)

print(f"Manifest wurde erstellt: {output_path}")
