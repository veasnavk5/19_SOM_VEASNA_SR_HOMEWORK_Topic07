"""
harness.py
----------
Everything that must NOT be trusted to "the model said so":
 - Permission control (role -> allowed tools), enforced in application code.
 - Input validation (delegates to schemas.py validators).
 - Safe execution / structured error handling (never leak raw exceptions).
 - A hard cap on tool calls per run (loop-guard).

This is the single choke point every tool call passes through.
"""

from typing import Any, Dict

from schemas import VALIDATORS, ValidationError
from tools import TOOL_IMPLEMENTATIONS

# ---------------------------------------------------------------------------
# C. Permission table (application code, not prompt text)
# ---------------------------------------------------------------------------
# Action           Customer   Admin
# search_products    yes       yes
# check_stock        yes       yes
# buy_product        yes       yes
# delete_product     no        yes

PERMISSIONS = {
    "customer": {"search_products", "check_stock", "buy_product"},
    "admin":    {"search_products", "check_stock", "buy_product", "delete_product"},
}

MAX_TOOL_CALLS_PER_RUN = 6  # D. Safety: hard iteration / tool-call limit


class PermissionError_(Exception):
    """Raised when a role attempts a tool it is not allowed to call."""
    def __init__(self, role: str, tool: str):
        self.role = role
        self.tool = tool
        super().__init__(f"role '{role}' is not permitted to call '{tool}'")


class ToolCallBudgetExceeded(Exception):
    """Raised when a single agent run exceeds MAX_TOOL_CALLS_PER_RUN."""
    pass


class Harness:
    """
    Wraps tool execution with permission checks, validation, and a call budget.
    The agent NEVER calls tools.py directly -- it always goes through here.
    """

    def __init__(self, role: str, max_calls: int = MAX_TOOL_CALLS_PER_RUN):
        if role not in PERMISSIONS:
            raise ValueError(f"Unknown role '{role}'. Known roles: {list(PERMISSIONS)}")
        self.role = role
        self.max_calls = max_calls
        self.calls_made = 0

    def is_permitted(self, tool_name: str) -> bool:
        return tool_name in PERMISSIONS.get(self.role, set())

    def call_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute one tool call with full safety checks. Always returns a
        structured dict -- never raises out to the caller -- so the agent
        loop can uniformly "observe" the result, success or failure.
        """
        # 1. Loop / budget guard
        if self.calls_made >= self.max_calls:
            return {
                "ok": False,
                "error": {
                    "code": "MAX_TOOL_CALLS_EXCEEDED",
                    "message": f"Stopped after {self.max_calls} tool calls to prevent an endless loop.",
                },
            }

        # 2. Tool must exist (allowlist -- reject anything not explicitly registered)
        if tool_name not in TOOL_IMPLEMENTATIONS:
            return {"ok": False, "error": {"code": "UNKNOWN_TOOL", "message": f"No such tool: {tool_name}"}}

        # 3. Permission check -- enforced here, in code, not just described in a prompt
        if not self.is_permitted(tool_name):
            return {
                "ok": False,
                "error": {
                    "code": "PERMISSION_DENIED",
                    "message": f"Role '{self.role}' is not allowed to call '{tool_name}'.",
                },
            }

        # 4. Input validation
        try:
            validator = VALIDATORS[tool_name]
            clean_args = validator(args)
        except ValidationError as e:
            return {"ok": False, "error": {"code": e.code, "message": e.message}}

        # 5. Execute, with a safety net around unexpected exceptions
        self.calls_made += 1
        try:
            implementation = TOOL_IMPLEMENTATIONS[tool_name]
            result = implementation(**clean_args)
            return result
        except Exception as e:  # pragma: no cover - defensive catch-all
            return {
                "ok": False,
                "error": {"code": "TOOL_EXECUTION_ERROR", "message": str(e)},
            }
