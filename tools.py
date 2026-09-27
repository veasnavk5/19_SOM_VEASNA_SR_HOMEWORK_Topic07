"""
tools.py
--------
Actual tool implementations (business logic). These are plain Python
functions operating on an in-memory "database". No external services,
no API keys required.

Each function returns a structured result dict of the shape:
    {"ok": True,  "data": {...}}
or
    {"ok": False, "error": {"code": "...", "message": "..."}}

so the agent can OBSERVE a machine-readable result instead of a raw
exception (see harness.py for where exceptions get converted to this
shape for validation/permission errors too).
"""

from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# In-memory product catalog ("database")
# ---------------------------------------------------------------------------

_PRODUCTS: List[Dict[str, Any]] = [
    {"id": 1, "name": "Aurora 14 Laptop",       "category": "laptop",     "price": 999.00, "stock": 5},
    {"id": 2, "name": "Nimbus Pro Laptop",       "category": "laptop",     "price": 1299.00, "stock": 0},
    {"id": 3, "name": "TrackMaster Mouse",       "category": "mouse",     "price": 25.00,  "stock": 40},
    {"id": 4, "name": "ClickyKey Mechanical Keyboard", "category": "keyboard", "price": 65.00, "stock": 12},
    {"id": 5, "name": "ViewFlat 27in Monitor",   "category": "monitor",   "price": 220.00, "stock": 3},
    {"id": 6, "name": "SilentSit Office Chair",  "category": "chair",     "price": 180.00, "stock": 0},
]


def _ok(data: Any) -> Dict[str, Any]:
    return {"ok": True, "data": data}


def _err(code: str, message: str) -> Dict[str, Any]:
    return {"ok": False, "error": {"code": code, "message": message}}


def _find_product(product_id: int):
    for p in _PRODUCTS:
        if p["id"] == product_id:
            return p
    return None


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def search_products(query: str) -> Dict[str, Any]:
    """Search catalog by substring match against name/category."""
    q = query.lower().strip()
    matches = [
        p for p in _PRODUCTS
        if q in p["name"].lower() or q in p["category"].lower()
    ]
    if not matches:
        return _err("NOT_FOUND", f"No products matched '{query}'")
    return _ok([dict(p) for p in matches])


def check_stock(product_id: int) -> Dict[str, Any]:
    """Return current stock for a product id."""
    product = _find_product(product_id)
    if product is None:
        return _err("PRODUCT_NOT_FOUND", f"No product with id {product_id}")
    return _ok({"product_id": product_id, "name": product["name"], "stock": product["stock"]})


def buy_product(product_id: int, quantity: int = 1) -> Dict[str, Any]:
    """Purchase `quantity` units of a product, decrementing stock."""
    product = _find_product(product_id)
    if product is None:
        return _err("PRODUCT_NOT_FOUND", f"No product with id {product_id}")
    if product["stock"] < quantity:
        return _err(
            "OUT_OF_STOCK",
            f"Requested {quantity} but only {product['stock']} of '{product['name']}' in stock",
        )
    product["stock"] -= quantity
    return _ok({
        "product_id": product_id,
        "name": product["name"],
        "purchased": quantity,
        "remaining_stock": product["stock"],
        "total_price": round(product["price"] * quantity, 2),
    })


def delete_product(product_id: int) -> Dict[str, Any]:
    """Permanently remove a product from the catalog. Admin-only (enforced in harness)."""
    product = _find_product(product_id)
    if product is None:
        return _err("PRODUCT_NOT_FOUND", f"No product with id {product_id}")
    _PRODUCTS.remove(product)
    return _ok({"deleted_product_id": product_id, "name": product["name"]})


# Registry mapping tool name -> callable implementation
TOOL_IMPLEMENTATIONS = {
    "search_products": search_products,
    "check_stock": check_stock,
    "buy_product": buy_product,
    "delete_product": delete_product,
}
