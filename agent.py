"""
agent.py
--------
The agent loop:

    User Request -> Agent decides -> Tool Call -> Tool Execution -> Result -> Agent decides again -> ... -> Final answer

IMPORTANT / DESIGN NOTE
------------------------
This homework asks for a *simple, self-contained* project that runs with
"just unzip and run" -- no API key. So instead of calling a real LLM, the
"Agent / LLM" box in the diagram is played by a small, transparent
rule-based planner (`_decide_next_step`) that reads the user's request and
the tool results observed so far, and decides which tool to call next --
exactly the same responsibility a real LLM would have in this slot.

Everything AROUND that decision point (schema-defined tools, structured
tool results, permission checks, validation, iteration limit, final-answer
synthesis) is real and works exactly like it would with a real model.
Swapping `_decide_next_step` for an actual call to an LLM API (e.g. via
the Anthropic Messages API with tool_use) would drop in without changing
anything else in this file's surrounding structure.

The available tools and their schemas are advertised via
`schemas.ALL_SCHEMAS`, exactly as you'd hand them to a real LLM's
function-calling / tool_use parameter.
"""

import re
from typing import Any, Dict, List, Optional

from harness import Harness
from schemas import ALL_SCHEMAS

CATALOG_KEYWORDS = ["laptop", "mouse", "keyboard", "monitor", "chair"]


class AgentRun:
    """Holds the full trace of one agent run: decisions, tool calls, results."""

    def __init__(self, user_request: str, role: str):
        self.user_request = user_request
        self.role = role
        self.trace: List[Dict[str, Any]] = []
        self.final_answer: Optional[str] = None

    def log(self, step_type: str, **payload):
        self.trace.append({"type": step_type, **payload})

    def print_trace(self):
        print(f"\nUser ({self.role}): {self.user_request}")
        for step in self.trace:
            if step["type"] == "decision":
                print(f"  [agent decides] {step['note']}")
            elif step["type"] == "tool_call":
                print(f"  [tool call]     {step['tool']}({step['args']})")
            elif step["type"] == "tool_result":
                if step["result"].get("ok"):
                    print(f"  [observation]   OK -> {step['result']['data']}")
                else:
                    err = step["result"]["error"]
                    print(f"  [observation]   ERROR {err['code']} -> {err['message']}")
        print(f"  [final answer]  {self.final_answer}\n")


class ShoppingAgent:
    """
    A small agent that fulfils shopping-style requests using the
    search_products / check_stock / buy_product / delete_product tools,
    subject to the permission and safety rules enforced in harness.py.
    """

    def __init__(self, role: str):
        self.harness = Harness(role=role)
        self.role = role

    # -----------------------------------------------------------------
    # Public entry point
    # -----------------------------------------------------------------
    def run(self, user_request: str) -> AgentRun:
        run = AgentRun(user_request=user_request, role=self.role)
        intent = self._parse_intent(user_request)

        # Step 1: does the request need a tool at all?
        if not intent["needs_tool"]:
            run.log("decision", note="Request does not require a tool. Answering directly.")
            run.final_answer = (
                "I can help with searching products, checking stock, buying, "
                "or (admin only) deleting a product. Could you rephrase your request?"
            )
            return run

        # Step 2: SEARCH (almost every shopping request starts here)
        run.log("decision", note=f"Request mentions '{intent['keyword']}'. Searching catalog first.")
        search_result = self._call(run, "search_products", {"query": intent["keyword"]})

        if not search_result.get("ok"):
            run.final_answer = f"I couldn't complete your request: {search_result['error']['message']}"
            return run

        candidates = search_result["data"]
        top_product = candidates[0]  # naive "pick best match" -- first result
        run.log(
            "decision",
            note=f"Found {len(candidates)} match(es). Using top match: "
                 f"'{top_product['name']}' (id={top_product['id']}).",
        )

        # Step 3: does the user care about stock/availability, buying, or deleting?
        if intent["action"] == "delete":
            del_result = self._call(run, "delete_product", {"product_id": top_product["id"]})
            if del_result.get("ok"):
                run.final_answer = f"Deleted product '{del_result['data']['name']}' (id={top_product['id']})."
            else:
                run.final_answer = f"Could not delete product: {del_result['error']['message']}"
            return run

        # For "check stock" and "buy", we always check stock first (observe before acting)
        stock_result = self._call(run, "check_stock", {"product_id": top_product["id"]})
        if not stock_result.get("ok"):
            run.final_answer = f"Could not check stock: {stock_result['error']['message']}"
            return run

        stock = stock_result["data"]["stock"]

        if intent["action"] == "buy":
            if stock <= 0:
                run.log("decision", note="Stock is 0. Will not attempt purchase.")
                run.final_answer = (
                    f"'{top_product['name']}' is currently out of stock, so I did not place an order."
                )
                return run

            qty = intent["quantity"]
            run.log("decision", note=f"Stock available ({stock}). Attempting to buy quantity={qty}.")
            buy_result = self._call(run, "buy_product", {"product_id": top_product["id"], "quantity": qty})
            if buy_result.get("ok"):
                d = buy_result["data"]
                run.final_answer = (
                    f"Purchased {d['purchased']} x '{d['name']}' for ${d['total_price']}. "
                    f"Remaining stock: {d['remaining_stock']}."
                )
            else:
                run.final_answer = f"Purchase failed: {buy_result['error']['message']}"
            return run

        # Default action: just report search + stock findings
        run.final_answer = (
            f"Found '{top_product['name']}' (id={top_product['id']}), price ${top_product['price']}, "
            f"currently {'IN STOCK (' + str(stock) + ')' if stock > 0 else 'OUT OF STOCK'}."
        )
        return run

    # -----------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------
    def _call(self, run: AgentRun, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        run.log("tool_call", tool=tool_name, args=args)
        result = self.harness.call_tool(tool_name, args)
        run.log("tool_result", tool=tool_name, result=result)
        return result

    def _parse_intent(self, text: str) -> Dict[str, Any]:
        """
        Very small rule-based 'planner'. Stands in for the LLM's tool-choice
        step. Looks at the raw text and decides:
          - whether a tool is needed at all,
          - which catalog keyword to search for,
          - which follow-up action to take (buy / delete / just-report),
          - quantity, if buying.
        """
        lower = text.lower()

        keyword = next((k for k in CATALOG_KEYWORDS if k in lower), None)
        if keyword is None:
            return {"needs_tool": False}

        if re.search(r"\bdelete\b|\bremove\b", lower):
            action = "delete"
        elif re.search(r"\bbuy\b|\bpurchase\b|\border\b", lower):
            action = "buy"
        else:
            action = "report"  # e.g. "find a laptop that is in stock"

        qty_match = re.search(r"\b(\d+)\b", lower)
        quantity = int(qty_match.group(1)) if qty_match else 1

        return {
            "needs_tool": True,
            "keyword": keyword,
            "action": action,
            "quantity": quantity,
        }


def describe_available_tools() -> str:
    """Human-readable listing of every registered tool schema (for README/demo)."""
    lines = []
    for name, schema in ALL_SCHEMAS.items():
        lines.append(f"- {name}: {schema['description']}")
    return "\n".join(lines)
