import os
import asyncio
import yaml
from typing import Optional, List, Dict, Any
from elemm.core.manager import AIProtocolManager
from elemm.core.registry import MetadataRegistry
from elemm.gateways.fastapi import FastAPIGateway
from elemm.gateways.mcp_server import MCPGateway

# Mock Database
PRODUCTS = [
    {
        "id": "moog-1",
        "name": "Moog Grandmother (Bio-Link Edition)",
        "price": 899.00,
        "specs": "Analog semi-modular synthesizer with biological feedback loop.",
        "image_url": "https://images.unsplash.com/photo-1598488035139-bdbb2231ce04?q=80&w=400"
    },
    {
        "id": "roland-v",
        "name": "Roland Juno-60 (Neuro-Interface)",
        "price": 1200.00,
        "specs": "Classic DCO synth with integrated neural bridge for direct thought control.",
        "image_url": "https://images.unsplash.com/photo-1514336715114-eb0678d91203?q=80&w=400"
    },
    {
        "id": "synth-gen-x",
        "name": "Synth-Genesis X1",
        "price": 2500.00,
        "specs": "High-end bio-organic synthesizer. Actually breathes while playing.",
        "image_url": "https://images.unsplash.com/photo-1552248524-10d9a7e5832b?q=80&w=400"
    }
]

class ShopState:
    def __init__(self):
        self.cart = []
        self.logged_in = False
        self.current_user = None

state = ShopState()

def run_synth_shop():
    # 1. Load Registry & Manager
    config_path = os.path.join(os.path.dirname(__file__), "landmarks.yaml")
    registry = MetadataRegistry(config_path)
    manager = AIProtocolManager(registry=registry)
    
    # --- Registration: catalog ---
    
    @manager.landmark("catalog:list_products")
    async def list_products():
        return {"products": [{"id": p["id"], "name": p["name"], "price": p["price"]} for p in PRODUCTS]}
    
    @manager.landmark("catalog:get_details")
    async def get_details(product_id: str):
        product = next((p for p in PRODUCTS if p["id"] == product_id), None)
        if not product:
            return {"status": "error", "message": f"Product {product_id} not found."}
        return product

    # --- Registration: auth ---
    
    @manager.landmark("auth:login")
    async def login(username: str, passkey: str):
        if passkey == "runner-2049":
            state.logged_in = True
            state.current_user = username
            return {"status": "success", "token": "jwt-cyber-12345", "message": f"Welcome back, {username}."}
        return {"status": "error", "message": "Invalid biometric passkey."}

    # --- Registration: cart ---
    
    @manager.landmark("cart:add_item")
    async def add_item(product_id: str, quantity: int = 1):
        if quantity <= 0:
            return {"status": "error", "message": "Quantity must be at least 1."}
            
        if not state.logged_in:
            return {"status": "error", "message": "Authentication required to access cart. Please login via auth:login."}
        
        product = next((p for p in PRODUCTS if p["id"] == product_id), None)
        if not product:
            return {"status": "error", "message": "Product not found."}
        
        state.cart.append({"id": product_id, "name": product["name"], "price": product["price"], "qty": quantity})
        total = sum(item["price"] * item["qty"] for item in state.cart)
        
        return {
            "status": "success",
            "cart_count": len(state.cart),
            "total": total,
            "message": f"Added {quantity}x {product['name']} to your cart."
        }

    @manager.landmark("cart:view_cart")
    async def view_cart():
        if not state.logged_in:
            return {"status": "error", "message": "Authentication required."}
        
        total = sum(item["price"] * item["qty"] for item in state.cart)
        return {"items": state.cart, "total": total}

    # 2. Launch Gateway
    import sys
    if "--mcp" in sys.argv:
        # Native MCP Server
        server = MCPGateway(manager, server_name="Synth-Genesis-v2")
        server.run_stdio()
    else:
        from fastapi import FastAPI
        app = FastAPI(title="Synth-Genesis-v2")
        gateway = FastAPIGateway(manager)
        gateway.bind_to_app(app)
        
        print("Starting Synth Shop v2 on http://localhost:8004")
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8004)

if __name__ == "__main__":
    run_synth_shop()
