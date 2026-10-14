"""Print the agent team's activity live in a terminal, from the backend's /api/events.

    .venv/bin/python backend/watch_agents.py
"""

import json
import time
import urllib.request

API = "http://localhost:8000/api/events"
COLORS = {"boss": "34", "inventory": "36", "accounting": "32", "facilities": "33", "customer_service": "35"}
NAMES = {"boss": "Boss", "inventory": "Inventory", "accounting": "Accounting",
         "facilities": "Facilities", "customer_service": "Customer Service"}


def tag(agent: str | None) -> str:
    if not agent:
        return "\033[1mDesk\033[0m"
    return f"\033[1;{COLORS.get(agent, '37')}m{NAMES.get(agent, agent)}\033[0m"


def show(e: dict) -> None:
    t, a = e["type"], e.get("agent")
    pad = "  " * max(len(e.get("chain") or [1]) - 1, 0)
    if t == "run_start":
        print(f"\n\033[1;44m RUN {e['run_id']} \033[0m ticket {e.get('ticket_id')}: {e['text']}")
    elif t == "reset":
        print("\n\033[1;43m RESET \033[0m working database restored from the original")
    elif t == "user_prompt":
        print(f"{pad}{tag(e.get('asked_by') if e.get('asked_by') != 'dashboard' else None)} \033[2m→\033[0m {tag(a)}  \033[3m{e['text'][:160]}\033[0m")
    elif t == "model_response":
        if e.get("text"):
            print(f"{pad}{tag(a)}: {e['text'][:300]}")
        for tool in e.get("mcp_tools", []):
            print(f"{pad}{tag(a)} \033[2mMCP\033[0m {tool['tool']} {json.dumps(tool['args'])[:120]}")
        for d in e.get("delegations", []):
            print(f"{pad}{tag(a)} delegates to {tag(d['to'])}")
    elif t == "end" and a:
        print(f"{pad}{tag(a)} \033[2mreported back:\033[0m {(e.get('text') or '')[:300]}")
    elif t == "error":
        print(f"\033[31mERROR\033[0m {e.get('text')}")
    elif t == "run_end":
        u = e.get("usage") or {}
        print(f"\033[1;42m RUN {e.get('status', 'done').upper()} \033[0m {u.get('requests')} model calls, "
              f"{u.get('tool_calls')} tool calls, {e.get('delegations')} delegations\n")


def main() -> None:
    since = -1
    print("Watching agent activity (Ctrl-C to stop)...")
    while True:
        try:
            with urllib.request.urlopen(f"{API}?since={since}&limit=1000", timeout=5) as r:
                data = json.load(r)
            for e in data["events"]:
                show(e)
            since = max(since, data["last_id"])
        except OSError:
            print("\033[2m(waiting for the backend on :8000)\033[0m")
            time.sleep(3)
        time.sleep(1)


if __name__ == "__main__":
    main()
