import sys
import json
from pathlib import Path
from datetime import datetime

data = sys.stdin.read()
Path("D:/AI/Claude_Switcher/hook_dump.jsonl").open("a").write(
    json.dumps({"ts": datetime.now().isoformat(), "raw": data}) + "\n"
)
