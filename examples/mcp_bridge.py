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
    read_only = os.environ.get("LANDMARK_READ_ONLY", "false").lower() == "true"
    
    for base_url in urls:
        base_url = base_url.strip()
        if not base_url: continue
        
        try:
            # Manifest abrufen (optional im Read-Only Modus)
            url_with_params = base_url
            if read_only:
                url_with_params = f"{base_url.rstrip('/')}/?read_only=true"
                
            manifest = await fetch_manifest(url_with_params)
            print(f"Lade Landmarks von {base_url} (Read-Only: {read_only})...")
            
            for action in manifest.get("actions", []):
                if action.get("hidden"): continue
                
                # Wir nutzen eine Factory-Funktion, um den Scope (Closure) für jedes Tool sauber zu trennen
                def create_tool(act, base):
                    @mcp.tool(name=act["id"])
                    async def landmark_tool(**kwargs):
                        return await call_landmark(base, act, kwargs)
                    
                    # Dokumentation patchen
                    doc = act.get("description", "Landmark Action")
                    if act.get("instructions"):
                        doc += f"\n\nRules: {act['instructions']}"
                    if act.get("remedy"):
                        doc += f"\n\nRemedy: {act['remedy']}"
                    
                    landmark_tool.__doc__ = doc
                    return landmark_tool

                create_tool(action, base_url)
                print(f"  -> Tool '{action['id']}' registriert.")
                
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
