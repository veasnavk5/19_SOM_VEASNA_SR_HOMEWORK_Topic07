"""
main.py
-------
Entry point. Runs a fixed demo (matching the README's Example Run section)
and then drops into an interactive prompt so you can try your own requests.

Usage:
    python3 main.py            # runs demo scenarios, then interactive mode
    python3 main.py --demo-only

No API key, no external packages, no internet connection required.
"""

import sys

from agent import ShoppingAgent, describe_available_tools


DEMO_SCENARIOS = [
    # (role, request)
    ("customer", "Find a laptop that is currently in stock"),
    ("customer", "I want to buy 2 keyboards"),
    ("customer", "Buy 10 office chairs"),          # triggers OUT_OF_STOCK path
    ("customer", "Delete the mouse from the catalog"),  # triggers PERMISSION_DENIED
    ("admin", "Delete the mouse from the catalog"),     # admin is allowed
]


def run_demo():
    print("=" * 70)
    print("SHOPPING AGENT -- DEMO RUN")
    print("=" * 70)
    print("\nAvailable tools:")
    print(describe_available_tools())
    print()

    for role, request in DEMO_SCENARIOS:
        agent = ShoppingAgent(role=role)
        run = agent.run(request)
        run.print_trace()


def run_interactive():
    print("=" * 70)
    print("INTERACTIVE MODE  (type 'quit' to exit)")
    print("=" * 70)
    print("Try things like:")
    print('  - "search for monitor"')
    print('  - "buy 3 mice"')
    print('  - "delete the chair"   (try as customer, then as admin)')
    print()

    while True:
        role = input("Role [customer/admin] (default customer): ").strip().lower() or "customer"
        if role in ("quit", "exit"):
            break
        if role not in ("customer", "admin"):
            print("Unknown role, defaulting to 'customer'.\n")
            role = "customer"

        request = input("Your request: ").strip()
        if request.lower() in ("quit", "exit"):
            break
        if not request:
            continue

        agent = ShoppingAgent(role=role)
        run = agent.run(request)
        run.print_trace()


if __name__ == "__main__":
    run_demo()
    if "--demo-only" not in sys.argv:
        try:
            run_interactive()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
