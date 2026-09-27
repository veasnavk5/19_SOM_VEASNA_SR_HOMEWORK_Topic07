# Shopping Agent — Simple Tool-Using Agent Loop

A small agentic application that receives a user request, decides whether a
tool is needed, calls the right tool(s) with structured arguments, observes
the results, and produces a final answer — with permission control and
basic safety enforced in application code.

**No API key needed.** Pure Python 3 standard library only. Unzip and run.

## Run it

```bash
cd my-agent
python3 main.py
```

This prints a demo run (5 fixed scenarios matching the Example Run section
below), then drops you into an interactive prompt where you can type your
own requests and pick a role (`customer` or `admin`).

Run only the demo, no prompt:
```bash
python3 main.py --demo-only
```

Requirements: Python 3.8+. No `pip install` needed — zero third-party dependencies.

---

## 1. Project Overview

The agent is a **Shopping Agent**. Given a natural-language request like
*"Find a laptop that is currently in stock"* or *"buy 2 keyboards"*, it:

1. figures out whether it needs to use a tool,
2. searches an in-memory product catalog,
3. checks stock,
4. optionally buys or (admin-only) deletes a product,
5. returns a final, human-readable answer built from what it actually observed.

**Note on the "Agent / LLM" box:** to keep the project runnable with zero
setup and no API key, the tool-choice step is done by a small, transparent
rule-based planner (`agent.py: _decide_next_step`/`_parse_intent`) instead of
a live LLM call. It occupies exactly the same slot a real LLM would in the
agent loop — reads the request + prior tool results, decides the next tool
call — and every tool result it receives is genuinely machine-observed data
from `tools.py`, not scripted output. All the actual homework requirements
(schemas, permission checks, validation, iteration limits, structured
errors) are enforced independently of how that decision is made, so swapping
in a real Anthropic API `tool_use` call would be a drop-in replacement for
just that one function.

## 2. Available Tools

| Tool | Description |
|---|---|
| `search_products(query)` | Searches the catalog by free-text match against product name/category. |
| `check_stock(product_id)` | Returns current stock quantity for a given product id. |
| `buy_product(product_id, quantity=1)` | Purchases units of a product; fails with `OUT_OF_STOCK` if not enough stock. |
| `delete_product(product_id)` | Permanently removes a product from the catalog. **Admin only.** |

Each tool has:
- an **implementation** in `tools.py` (real logic, in-memory product "database"),
- an explicit **JSON-Schema-style input schema** in `schemas.py` (`ALL_SCHEMAS`), describing required fields, types, and constraints, plus a matching runtime **validator** function.

## 3. Agent Loop

```
User Request
   │
   ▼
Agent decides: does this need a tool? which one? what arguments?
   │
   ▼
Harness: permission check → input validation → iteration-limit check
   │
   ▼
Tool Execution (tools.py)
   │
   ▼
Structured Result observed by Agent  { ok: true/false, data / error }
   │
   ▼
Agent decides next step based on the result
   (e.g. only check stock after a successful search;
    only attempt to buy if stock > 0;
    stop and report if an error was observed)
   │
   ▼
Final Answer
```

Concretely, for a buy request, the loop runs:
`search_products` → observe candidates → `check_stock` → observe quantity →
(if in stock) `buy_product` → observe purchase result → final answer.
Each step's decision depends on the *previous* tool's observed result, which
is the core requirement of the assignment (not just one blind tool call).

## 4. Permission Rule

Enforced in `harness.py` (`PERMISSIONS` dict + `Harness.call_tool`), **not**
just described to the model:

| Action | Customer | Admin |
|---|:---:|:---:|
| `search_products` | ✓ | ✓ |
| `check_stock` | ✓ | ✓ |
| `buy_product` | ✓ | ✓ |
| `delete_product` | ✗ | ✓ |

If a `customer` role attempts `delete_product`, the harness returns a
structured `PERMISSION_DENIED` error **before** the tool implementation ever
runs — the check happens in code regardless of what the request text says.

## 5. Safety

All enforced in `harness.py` / `schemas.py`:

- **Input validation**: every tool has a validator (`schemas.py`) checking
  types and constraints before execution — e.g. `product_id` must be a
  positive integer, `quantity` must be a positive integer. Invalid input
  returns a structured `INVALID_INPUT` error instead of crashing or
  silently proceeding.
- **Error handling**: tool failures (not found, out of stock, permission
  denied, bad input, unknown tool) are all returned as structured
  `{ok: False, error: {code, message}}` results rather than raw exceptions.
  Unexpected exceptions inside a tool are also caught and converted to a
  `TOOL_EXECUTION_ERROR` result so the process never crashes.
- **Iteration / tool-call limit**: `Harness(max_calls=6)` (default) hard-caps
  the number of tool calls in a single agent run. Once the budget is
  exhausted, further calls return `MAX_TOOL_CALLS_EXCEEDED` instead of
  looping forever.
- **Allowlist**: unrecognized tool names are rejected with `UNKNOWN_TOOL`
  before any execution is attempted.

## 6. Example Run

Input (`role=customer`): `"Find a laptop that is currently in stock"`

```
User (customer): Find a laptop that is currently in stock
  [agent decides] Request mentions 'laptop'. Searching catalog first.
  [tool call]     search_products({'query': 'laptop'})
  [observation]   OK -> [{'id': 1, 'name': 'Aurora 14 Laptop', ..., 'stock': 5},
                          {'id': 2, 'name': 'Nimbus Pro Laptop', ..., 'stock': 0}]
  [agent decides] Found 2 match(es). Using top match: 'Aurora 14 Laptop' (id=1).
  [tool call]     check_stock({'product_id': 1})
  [observation]   OK -> {'product_id': 1, 'name': 'Aurora 14 Laptop', 'stock': 5}
  [final answer]  Found 'Aurora 14 Laptop' (id=1), price $999.0, currently IN STOCK (5).
```

Permission-denied example (`role=customer`): `"Delete the mouse from the catalog"`

```
  [tool call]     delete_product({'product_id': 3})
  [observation]   ERROR PERMISSION_DENIED -> Role 'customer' is not allowed to call 'delete_product'.
  [final answer]  Could not delete product: Role 'customer' is not allowed to call 'delete_product'.
```

Same request as `role=admin` succeeds:
```
  [tool call]     delete_product({'product_id': 3})
  [observation]   OK -> {'deleted_product_id': 3, 'name': 'TrackMaster Mouse'}
  [final answer]  Deleted product 'TrackMaster Mouse' (id=3).
```

Running `python3 main.py --demo-only` reproduces all of the above plus an
`OUT_OF_STOCK` example (`"Buy 10 office chairs"`), in one shot.

---

## Project Structure

```
my-agent/
├── README.md        # this file
├── main.py           # entry point, demo scenarios + interactive CLI
├── agent.py           # agent loop, rule-based tool-choice "planner"
├── tools.py            # tool implementations + in-memory product catalog
├── schemas.py            # tool input schemas + validators
└── harness.py              # permission control, validation wiring, call-budget guard
```

## Checklist (self-assessment)

- [x] At least 2 tools available (4: search/check_stock/buy/delete)
- [x] Model/agent can choose and call a tool
- [x] Tool result returned to the agent and used to decide next step
- [x] Agent continues the loop after observing a result (search → stock → buy)
- [x] Tool inputs have a defined schema (`schemas.py`)
- [x] At least one permission rule enforced in application code (`harness.py`)
- [x] Basic validation implemented
- [x] Basic error handling implemented (structured errors, no raw crashes)
- [x] Max iteration/tool-call limit implemented
- [x] README + run instructions included
