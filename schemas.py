"""
schemas.py
----------
Explicit tool input schemas.

Each tool has a JSON-Schema-style dict (so it could be handed to a real LLM's
function-calling API unchanged) PLUS a small validate_* function that the
harness actually runs at execution time. The schema describes what a caller
is ALLOWED to send; the validate function is what the application ACTUALLY
enforces. This keeps "described in the prompt" separate from "checked in code".
"""

from typing import Any, Dict


class ValidationError(Exception):
    """Raised when tool arguments fail schema/business validation."""
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


# ---------------------------------------------------------------------------
# JSON-Schema-like definitions (what the model/agent is told is available)
# ---------------------------------------------------------------------------

SEARCH_PRODUCTS_SCHEMA = {
    "name": "search_products",
    "description": "Search the product catalog by a free-text query (matches name/category).",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "minLength": 1, "description": "Search text, e.g. 'laptop'"}
        },
        "required": ["query"],
    },
}

CHECK_STOCK_SCHEMA = {
    "name": "check_stock",
    "description": "Check current stock quantity for a specific product id.",
    "parameters": {
        "type": "object",
        "properties": {
            "product_id": {"type": "integer", "minimum": 1}
        },
        "required": ["product_id"],
    },
}

BUY_PRODUCT_SCHEMA = {
    "name": "buy_product",
    "description": "Purchase a quantity of a product. Fails if insufficient stock.",
    "parameters": {
        "type": "object",
        "properties": {
            "product_id": {"type": "integer", "minimum": 1},
            "quantity": {"type": "integer", "minimum": 1, "default": 1},
        },
        "required": ["product_id"],
    },
}

DELETE_PRODUCT_SCHEMA = {
    "name": "delete_product",
    "description": "Remove a product from the catalog permanently. Admin only.",
    "parameters": {
        "type": "object",
        "properties": {
            "product_id": {"type": "integer", "minimum": 1}
        },
        "required": ["product_id"],
    },
}

ALL_SCHEMAS = {
    "search_products": SEARCH_PRODUCTS_SCHEMA,
    "check_stock": CHECK_STOCK_SCHEMA,
    "buy_product": BUY_PRODUCT_SCHEMA,
    "delete_product": DELETE_PRODUCT_SCHEMA,
}


# ---------------------------------------------------------------------------
# Actual runtime validators (basic input validation requirement)
# ---------------------------------------------------------------------------

def validate_search_products(args: Dict[str, Any]) -> Dict[str, Any]:
    query = args.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValidationError("INVALID_INPUT", "query must be a non-empty string")
    return {"query": query.strip()}


def _validate_product_id(args: Dict[str, Any]) -> int:
    pid = args.get("product_id")
    if isinstance(pid, bool) or not isinstance(pid, int):
        raise ValidationError("INVALID_INPUT", "product_id must be an integer")
    if pid <= 0:
        raise ValidationError("INVALID_INPUT", "product_id must be a positive integer")
    return pid


def validate_check_stock(args: Dict[str, Any]) -> Dict[str, Any]:
    return {"product_id": _validate_product_id(args)}


def validate_buy_product(args: Dict[str, Any]) -> Dict[str, Any]:
    pid = _validate_product_id(args)
    qty = args.get("quantity", 1)
    if isinstance(qty, bool) or not isinstance(qty, int):
        raise ValidationError("INVALID_INPUT", "quantity must be an integer")
    if qty <= 0:
        raise ValidationError("INVALID_INPUT", "quantity must be a positive integer")
    return {"product_id": pid, "quantity": qty}


def validate_delete_product(args: Dict[str, Any]) -> Dict[str, Any]:
    return {"product_id": _validate_product_id(args)}


VALIDATORS = {
    "search_products": validate_search_products,
    "check_stock": validate_check_stock,
    "buy_product": validate_buy_product,
    "delete_product": validate_delete_product,
}
