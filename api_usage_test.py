"""
Quick test: call Anthropic API and inspect the usage fields returned.
Run: python api_usage_test.py
"""
import json
import urllib.request
from pathlib import Path

config = json.loads(Path("D:/AI/Claude_Switcher/config.json").read_text())
api_key = config["api_key"]

payload = json.dumps({
    "model": "claude-haiku-4-5-20251001",
    "max_tokens": 10,
    "messages": [{"role": "user", "content": "say hi"}],
}).encode()

req = urllib.request.Request(
    "https://api.anthropic.com/v1/messages",
    data=payload,
    headers={
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    },
)

with urllib.request.urlopen(req) as resp:
    body = json.loads(resp.read())

print(json.dumps(body, indent=2))
print("\n--- usage fields ---")
print(json.dumps(body.get("usage", {}), indent=2))
