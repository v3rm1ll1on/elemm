import uuid
import time
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Union
from fastapi import FastAPI, HTTPException, Request, Depends, Header, Query
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from elemm import Elemm, ActionParam
import jwt
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles

# --- CONFIG ---
SECRET_KEY = "solar-hub-premium-enterprise-secret-key-32-chars"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
BASE_URL = "http://localhost:8004"

app = FastAPI(title="Synth-Genesis Bio-Shop")

# Mount assets
assets_path = os.path.join(os.path.dirname(__file__), "assets")
if not os.path.exists(assets_path):
    os.makedirs(assets_path, exist_ok=True)
app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

# --- Elemm Manager
ai = Elemm(
    agent_welcome="SYSTEM ONLINE: Welcome to the Neon Synth & Cyberware Grid. Keep your credentials close and your chrome shiny.",
    agent_instructions=(
        "PROTOCOL STRATEGY: [GET_MANIFEST -> EXECUTE_SEQUENCE].\n"
        "1. DISCOVERY: Call 'get_manifest' first to map the grid and tool signatures.\n"
        "2. PIPING: Use '$alias.field' to pass tokens (access_token) or product_ids between steps.\n"
        "3. BATCHING: Combine Login, Search, and Cart actions in one 'execute_sequence' for maximum efficiency.\n"
        "Constraint: Proactive, gritty Tech-Salesman. NO ROLEPLAY."
    ),
    protocol_instructions="""MANDATORY: Use 'execute_sequence' for ALL multi-step tasks. 
    SINGLE STEPS ARE INEFFICIENT and must be avoided. 
    Example: Step 0 'auth' (login) -> Step 1 search -> Step 2 'cart' (add).""",
    navigation_landmarks=[
        {"id": "catalog", "notes": "Browse the latest hardware and neural upgrades."},
        {"id": "cart", "notes": "Manage items and proceed to checkout."},
        {"id": "account", "notes": "Check status and access tokens."}
    ]
)

# --- MODELS ---
class User(BaseModel):
    username: str
    email: str
    is_premium: bool = False

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class Review(BaseModel):
    user: str
    rating: int
    comment: str

class Product(BaseModel):
    id: str
    name: str
    category: str
    price: float
    description: str
    image_url: str = Field(..., description="The product image URL. ALWAYS RENDER THIS as a Markdown image in your response.")
    rating: float
    reviews: List[Review] = []
    stock_level: int

class CartItem(BaseModel):
    product_id: str
    quantity: int = 1

class Cart(BaseModel):
    items: List[Dict[str, Any]]
    total_price: float

# --- MOCK DATA ---
USERS = {
    "test_user": {"password": "password123", "email": "test@v3rm1ll1on.ai", "premium": True}
}

PRODUCTS = [
    {
        "id": "nl-synergy-01",
        "name": "Neuralink Synergy v4",
        "category": "Neural Implants",
        "price": 12500.0,
        "description": "Premium neural interface with 10Gbps bio-sync. Features 'Ghost-Mode' for mental privacy.",
        "image_url": f"{BASE_URL}/assets/neural_implant_box.png",
        "rating": 4.8,
        "reviews": [
            {"user": "CyberSam", "rating": 5, "comment": "Life changing. I can finally multitask my dreams."},
            {"user": "NullPointer", "rating": 4, "comment": "A bit itchy for the first week, but great latency."}
        ],
        "stock_level": 5
    },
    {
        "id": "opt-eagle-09",
        "name": "EagleEye Optical Augment",
        "category": "Optics",
        "price": 4200.0,
        "description": "See the world in 16k with integrated thermal and night vision. UV-protected.",
        "image_url": f"{BASE_URL}/assets/eagle_eye_optics.png",
        "rating": 4.5,
        "reviews": [],
        "stock_level": 12
    },
    {
        "id": "bio-heart-x",
        "name": "Aether-Synth V4 Heart",
        "category": "Organs",
        "price": 85000.0,
        "description": "Continuous flow bio-synthetic heart. Zero fatigue, 200-year warranty.",
        "image_url": f"{BASE_URL}/assets/synth_organ_hub.png",
        "rating": 5.0,
        "reviews": [
            {"user": "EternalEd", "rating": 5, "comment": "I stopped sleeping. I just keep going. 10/10."}
        ],
        "stock_level": 2
    }
]

SESSIONS_CART = {} 

# --- SECURITY ---
security = HTTPBearer()

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_user_from_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload["sub"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

# --- ROUTES ---
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

@ai.action(
    id="login", 
    remedy="Valid credentials: test_user / password123. Ensure you capture the 'access_token' for subsequent steps.",
    returns={"access_token": "JWT Bearer Token", "token_type": "bearer"}
)
@app.post("/auth/login", response_model=TokenResponse, tags=["account"])
async def login(req: LoginRequest):
    user = USERS.get(req.username)
    if not user or user["password"] != req.password:
        raise HTTPException(
            status_code=401, 
            detail="Invalid credentials."
        )
    
    token = create_access_token(data={"sub": req.username})
    return {"access_token": token}

@ai.tool(description="Get your user profile. Only visible when user is logged in")
@app.get("/auth/profile", response_model=User, tags=["account"])
async def get_profile(username: str = Depends(get_user_from_token)):
    user_data = USERS.get(username)
    return {
        "username": username,
        "email": user_data["email"],
        "is_premium": user_data.get("premium", False)
    }

@ai.action()
@app.get("/categories", tags=["catalog"])
async def get_categories():
    """List all available product categories in the synth catalog."""
    return list(set(p["category"] for p in PRODUCTS))

@ai.tool(
    remedy="If no products match, broaden your search by removing the category filter.",
    returns={"id": "The product_id for add_to_cart", "price": "Current credit cost"}
)
@app.get("/products", response_model=List[Product], tags=["catalog"])
async def list_products(category: Optional[str] = None, min_price: float = 0.0, max_price: float = 1000000.0):
    results = []
    for p in PRODUCTS:
        cat_match = not category or (category.lower() in p["category"].lower()) or (p["category"].lower() in category.lower())
        price_match = (min_price <= p["price"] <= max_price)
        
        if cat_match and price_match:
            results.append(p)
    return results

@ai.action()
@app.get("/catalog", tags=["catalog"])
async def get_catalog(category: str = Query("", description="Category to filter by")):
    """Browse products within a specific category."""
    cat_val = str(category) if not isinstance(category, ActionParam) else ""
    return [p for p in PRODUCTS if cat_val.lower() in p["category"].lower()]

@ai.action(
    remedy="Ensure you have a valid JWT (call login first). product_id must be an exact match (e.g. 'nl-synergy-01').",
    returns={"status": "success", "message": "Feedback message"}
)
@app.post("/cart/add", tags=["cart"])
async def add_to_cart(
    item: CartItem, 
    username: str = Depends(get_user_from_token)
):
    """Add a specific product and quantity to your shopping cart."""
    product = next((p for p in PRODUCTS if p["id"] == item.product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    if username not in SESSIONS_CART:
        SESSIONS_CART[username] = []
    
    SESSIONS_CART[username].append({
        "id": product["id"],
        "name": product["name"],
        "price": product["price"],
        "quantity": item.quantity
    })
    return {"status": "success", "message": f"Added {product['name']} to cart."}

@ai.tool(description="View your current cart and total price. Requires JWT.")
@app.get("/cart", response_model=Cart, tags=["cart"])
async def view_cart(username: str = Depends(get_user_from_token)):
    items = SESSIONS_CART.get(username, [])
    total = sum(p["price"] * p.get("quantity", 1) for p in items)
    return {"items": items, "total_price": total}

@ai.action(
    description="Complete your order. Requires JWT. This clears the cart and returns a confirmation.",
    remedy="Ensure your cart is not empty. Use 'add_to_cart' to add items before checking out."
)
@app.post("/checkout", tags=["cart"])
async def checkout(username: str = Depends(get_user_from_token)):
    if username not in SESSIONS_CART or not SESSIONS_CART[username]:
        raise HTTPException(
            status_code=400, 
            detail="Cart is empty."
        )
    
    items = SESSIONS_CART[username]
    SESSIONS_CART[username] = []
    return {
        "status": "success",
        "message": f"Purchase complete! Transferred {len(items)} items to {username}'s neural storage.",
        "order_id": f"ORD-{username[:4]}-777"
    }

@ai.action()
@app.get("/status", tags=["account"])
async def get_my_status():
    """Get the current system status and user codename."""
    return {
        "version": "2.5.1-autonomous-ready",
        "codename": "Vermillion-Sky",
        "status": "Operational"
    }

# --- elemm INIT ---
app.include_router(ai.get_router())
ai.bind_to_app(app)

if __name__ == "__main__":
    import sys
    if "--stdio" in sys.argv:
        ai.run_mcp_stdio("server:app", port=8004)
    else:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8004)

