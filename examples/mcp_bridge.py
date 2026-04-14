import os
import json
import httpx
import asyncio
from typing import Dict, Any, List
from mcp.server.fastmcp import FastMCP

# Initialisierung des MCP Servers
mcp = FastMCP("Landmark Bridge")

# Hilfsfunktion zum Abrufen des Manifests
async def fetch_manifest(url: str) -> Dict[str, Any]:
    manifest_url = f"{url.rstrip('/')}/.well-known/llm-landmarks.json"
    async with httpx.AsyncClient() as client:
        resp = await client.get(manifest_url)
        resp.raise_for_status()
        return resp.json()

# Hilfsfunktion zum Ausführen einer Landmark-Aktion
async def call_landmark(base_url: str, action: Dict[str, Any], arguments: Dict[str, Any]) -> str:
    method = action["method"]
    url = action["url"]
    
    # URL Parameter ersetzen (z.B. /items/{id})
    target_url = url
    remaining_args = arguments.copy()
    for key, value in arguments.items():
        placeholder = "{" + key + "}"
        if placeholder in target_url:
            target_url = target_url.replace(placeholder, str(value))
            remaining_args.pop(key)

    # Absolute URL bauen
    if not target_url.startswith("http"):
        target_url = f"{base_url.rstrip('/')}/{target_url.lstrip('/')}"

    # Header-Injektion für Auth
    headers = {}
    if "authorization" in remaining_args:
        headers["Authorization"] = remaining_args.pop("authorization")
    elif "x_api_key" in remaining_args:
        headers["X-API-Key"] = remaining_args.pop("x_api_key")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            if method.upper() == "GET":
                resp = await client.get(target_url, params=remaining_args, headers=headers)
            else:
                resp = await client.request(method, target_url, json=remaining_args, headers=headers)
            
            if resp.status_code >= 400:
                return f"Error {resp.status_code}: {resp.text}"
            return resp.text
        except Exception as e:
            return f"Fehler beim Aufruf der Landmark: {str(e)}"

# Dynamische Registrierung der Tools beim Start
async def initialize():
    urls = os.environ.get("LANDMARK_URLS", "http://localhost:8004").split(",")
    
    for base_url in urls:
        base_url = base_url.strip()
        if not base_url: continue
        
        try:
            manifest = await fetch_manifest(base_url)
            print(f"Lade Landmarks von {base_url}...")
            
            for action in manifest.get("actions", []):
                if action.get("hidden"): continue
                
                action_id = action["id"]
                # Wir erzeugen eine lokale Kopie der Action für den Closure
                current_action = action
                current_base = base_url

                @mcp.tool(name=action_id)
                async def landmark_tool(ctx_action=current_action, ctx_base=current_base, **kwargs):
                    """
                    Dynamisch generiertes Landmark-Tool.
                    """
                    # Wir nutzen den Docstring der Action für die KI-Beschreibung
                    return await call_landmark(ctx_base, ctx_action, kwargs)

                # Wir müssen den Docstring und die Beschreibung manuell patchen, 
                # da FastMCP sie normalerweise aus der Funktionssignatur zieht.
                landmark_tool.__doc__ = action.get("description", "Landmark Action")
                if action.get("instructions"):
                    landmark_tool.__doc__ += f"\nRules: {action['instructions']}"
                
                print(f"  -> Tool '{action_id}' registriert.")
                
        except Exception as e:
            print(f"Fehler beim Laden von {base_url}: {e}")

if __name__ == "__main__":
    # Wir führen die Initialisierung aus, bevor wir den Server starten
    # Hinweis: In einer echten MCP Umgebung würde man hier mcp.run() nutzen
    # Für dieses Skript nutzen wir FastMCP asynchron
    import sys
    
    # Initialisierung triggern
    asyncio.run(initialize())
    
    # Server im Stdio-Modus starten
    mcp.run()
