# 🦾 Synth-Genesis Bio-Shop (v2)

This example demonstrates a high-fidelity E-commerce implementation using the Elemm v2 architecture.

## 🌟 Key Features
- **Landmark Namespacing**: Tools are grouped into `catalog`, `cart`, and `auth`.
- **Identity Enforcement**: The cart requires a valid login session.
- **Visual-Ready Data**: Product details include image URLs for AI rendering.
- **Smart Piping**: Shows how to pipe product IDs from discovery to purchase.

## 🚀 Running the Example

### 1. As a FastAPI Gateway (Recommended)
This launches a web server with discovery endpoints.
```bash
PYTHONPATH=src python3 examples/synth_shop/synth_shop_v2.py --fastapi
```
Access the manifest at: `http://localhost:8004/.well-known/elemm-manifest.md`

### 2. As a Native MCP Server
This runs the shop as a standard MCP toolset over STDIO.
```bash
PYTHONPATH=src python3 examples/synth_shop/synth_shop_v2.py
```

## 🧪 Testing with Piping
The agent can perform a full purchase in one turn:
1. `catalog:list_products` -> `$list`
2. `auth:login` -> `$user`
3. `cart:add_item(product_id=$list.products[0].id)`
4. `cart:view_cart()`
