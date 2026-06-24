"""
Parse a Claude Code transcript .jsonl and update usage_history.json.
Called by the Stop hook (reads payload from stdin) or directly:
  python usage_summary.py <transcript_path> [session_id]
"""
import sys
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

HISTORY_FILE = Path("D:/AI/Claude_Switcher/usage_history.json")

PRICING = {
    "claude-sonnet-4-6":         {"input": 3.00,  "output": 15.00, "cache_write": 3.75,  "cache_read": 0.30},
    "claude-haiku-4-5-20251001": {"input": 0.80,  "output": 4.00,  "cache_write": 1.00,  "cache_read": 0.08},
    "claude-opus-4-8":           {"input": 15.00, "output": 75.00, "cache_write": 18.75, "cache_read": 1.50},
}
DEFAULT_PRICE = {"input": 3.00, "output": 15.00, "cache_write": 3.75, "cache_read": 0.30}


def calc_cost(model, usage):
    p = PRICING.get(model, DEFAULT_PRICE)
    M = 1_000_000
    return (
        usage["input_tokens"] * p["input"] / M
        + usage["output_tokens"] * p["output"] / M
        + usage.get("cache_creation_input_tokens", 0) * p["cache_write"] / M
        + usage.get("cache_read_input_tokens", 0) * p["cache_read"] / M
    )


def load_history() -> list:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def summarize(transcript_path, session_id=None):
    totals = defaultdict(lambda: defaultdict(int))

    seen_requests = set()
    for line in Path(transcript_path).read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("type") != "assistant":
            continue
        req_id = row.get("requestId", row.get("uuid"))
        if req_id in seen_requests:
            continue
        seen_requests.add(req_id)
        msg = row.get("message", {})
        model = msg.get("model", "unknown")
        usage = msg.get("usage")
        if not usage:
            continue
        t = totals[model]
        t["input_tokens"] += usage.get("input_tokens", 0)
        t["output_tokens"] += usage.get("output_tokens", 0)
        t["cache_creation_input_tokens"] += usage.get("cache_creation_input_tokens", 0)
        t["cache_read_input_tokens"] += usage.get("cache_read_input_tokens", 0)

    if not totals:
        print("No usage data found.")
        return

    grand_cost = sum(calc_cost(m, u) for m, u in totals.items())
    models_out = {m: {**u, "cost": calc_cost(m, u)} for m, u in totals.items()}

    for model, u in totals.items():
        print(f"\nModel: {model}")
        print(f"  input  : {u['input_tokens']:>10,}")
        print(f"  output : {u['output_tokens']:>10,}")
        print(f"  cost   : ${calc_cost(model, u):.6f}")
    print(f"\nSession total: ${grand_cost:.6f}")

    # Upsert into history: update existing session_id row, or append new
    history = load_history()
    ts_str = datetime.now().strftime("%m-%d %H:%M")

    entry = {
        "ts": ts_str,
        "session_id": session_id or "",
        "models": models_out,
        "total_cost": grand_cost,
    }

    if session_id:
        for i, h in enumerate(history):
            if h.get("session_id") == session_id:
                history[i] = entry
                break
        else:
            history.append(entry)
    else:
        history.append(entry)

    HISTORY_FILE.write_text(json.dumps(history, indent=2), encoding="utf-8")
    print(f"\nHistory updated ({len(history)} sessions).")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        summarize(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    else:
        raw = sys.stdin.read()
        if not raw.strip():
            print("No transcript path provided.")
            sys.exit(1)
        payload = json.loads(raw)
        summarize(payload.get("transcript_path", ""),
                  session_id=payload.get("session_id"))
