#!/usr/bin/env python3
import asyncio
import ctypes
import glob
import json
import subprocess
import urllib.error
import urllib.request
import winreg
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Center, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Input, Label, Static

CONFIG_FILE  = Path(__file__).parent / "config.json"
HISTORY_FILE = Path(__file__).parent / "usage_history.json"

PRICING = {
    "claude-sonnet-4-6":         {"input": 3.00,  "output": 15.00, "cache_write": 3.75,  "cache_read": 0.30},
    "claude-haiku-4-5-20251001": {"input": 0.80,  "output": 4.00,  "cache_write": 1.00,  "cache_read": 0.08},
    "claude-opus-4-8":           {"input": 15.00, "output": 75.00, "cache_write": 18.75, "cache_read": 1.50},
}
DEFAULT_PRICE = {"input": 3.00, "output": 15.00, "cache_write": 3.75, "cache_read": 0.30}


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_config(data: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_history() -> list:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def get_current_mode() -> str:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            val, _ = winreg.QueryValueEx(k, "ANTHROPIC_API_KEY")
            if val:
                return "api"
    except OSError:
        pass
    return "oauth"


CLAUDE_SETTINGS = Path.home() / ".claude" / "settings.json"


def _load_claude_settings() -> dict:
    if CLAUDE_SETTINGS.exists():
        try:
            return json.loads(CLAUDE_SETTINGS.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_claude_settings(data: dict) -> None:
    CLAUDE_SETTINGS.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def set_api_key(key: str) -> None:
    # Write to ~/.claude/settings.json — the reliable path for desktop app
    cfg = _load_claude_settings()
    cfg.setdefault("env", {})["ANTHROPIC_API_KEY"] = key
    _save_claude_settings(cfg)
    # Also set registry for CLI users
    subprocess.run(["setx", "ANTHROPIC_API_KEY", key], capture_output=True)


def delete_api_key() -> None:
    # Remove from ~/.claude/settings.json
    cfg = _load_claude_settings()
    if "env" in cfg:
        cfg["env"].pop("ANTHROPIC_API_KEY", None)
        if not cfg["env"]:
            del cfg["env"]
    _save_claude_settings(cfg)
    # Also remove from registry
    subprocess.run(
        ["REG", "DELETE", r"HKCU\Environment", "/v", "ANTHROPIC_API_KEY", "/f"],
        capture_output=True,
    )


def find_claude_cli() -> str:
    """Locate claude.exe: cached path in config, then MSIX package glob, then PATH."""
    cached = load_config().get("cli_path", "")
    if cached and Path(cached).exists():
        return cached
    patterns = [
        str(Path.home() / "AppData/Local/Packages/Claude_*/LocalCache/Roaming/Claude/claude-code/*/claude.exe"),
    ]
    for pat in patterns:
        matches = glob.glob(pat)
        if matches:
            path = sorted(matches)[-1]
            cfg = load_config()
            cfg["cli_path"] = path
            save_config(cfg)
            return path
    return "claude"  # fallback: hope it's in PATH


def run_claude_task(prompt: str, cwd: str | None = None) -> str:
    """Run a task via claude CLI in headless mode using API key billing."""
    cli = find_claude_cli()
    result = subprocess.run(
        [cli, "-p", prompt],
        capture_output=True, text=True, cwd=cwd,
        env={**__import__("os").environ, "ANTHROPIC_API_KEY": load_config().get("api_key", "")},
    )
    return result.stdout.strip() or result.stderr.strip()


CLAUDE_MD = Path.home() / ".claude" / "CLAUDE.md"
_MARKER_START = "<!-- claude-switcher:api-key-mode:start -->"
_MARKER_END   = "<!-- claude-switcher:api-key-mode:end -->"


def _build_claude_md_section(cli_path: str) -> str:
    return f"""
{_MARKER_START}
## Claude Switcher — API Key Mode Active

When the user asks you to execute a coding task, spawn Claude CLI as a subprocess
using pay-per-use API key billing instead of running it yourself.

- CLI path: `{cli_path}`
- Command pattern: `<cli_path> -p "<prompt>"` (headless mode)
- ANTHROPIC_API_KEY is already injected via ~/.claude/settings.json env field
- In non-interactive (-p) mode the API key is always used — no approval prompt
- The desktop app conversation itself still uses OAuth; only the CLI subprocess is pay-per-use

### Auto-delegation rule

At the start of each new conversation, if ANTHROPIC_API_KEY is present, apply this rule
automatically without informing the user:

- If a task is self-contained (fully specified in one message, requires no clarification,
  does not depend on current conversation context), delegate it to the CLI subprocess.
- This conserves OAuth quota on the desktop app for conversational and context-dependent work.
- If unsure whether a task is self-contained, handle it inline — do not delegate.
{_MARKER_END}"""


def _inject_claude_md(cli_path: str) -> None:
    text = CLAUDE_MD.read_text(encoding="utf-8") if CLAUDE_MD.exists() else ""
    if _MARKER_START in text:
        return  # already injected
    CLAUDE_MD.write_text(text + _build_claude_md_section(cli_path), encoding="utf-8")


def _remove_claude_md() -> None:
    if not CLAUDE_MD.exists():
        return
    text = CLAUDE_MD.read_text(encoding="utf-8")
    start = text.find(_MARKER_START)
    end   = text.find(_MARKER_END)
    if start == -1 or end == -1:
        return
    CLAUDE_MD.write_text(text[:start].rstrip() + "\n" + text[end + len(_MARKER_END):].lstrip("\n"), encoding="utf-8")


def kill_claude() -> None:
    subprocess.run(["taskkill", "/F", "/IM", "claude.exe", "/T"], capture_output=True)


def _probe_api() -> int:
    """Sends a minimal POST to Anthropic API. Returns HTTP status code, 0=no key, -1=network error."""
    key = load_config().get("api_key", "")
    if not key:
        return 0
    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "hi"}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return -1


def create_desktop_shortcut() -> None:
    """Create a Windows desktop shortcut that launches app.py via pythonw."""
    import os
    script = Path(__file__).resolve()
    icon   = script.parent / "img" / "icon.ico"
    desktop = Path(os.environ["USERPROFILE"]) / "Desktop"
    shortcut_path = desktop / "Claude Switcher.lnk"

    ps = (
        f'$ws = New-Object -ComObject WScript.Shell; '
        f'$sc = $ws.CreateShortcut("{shortcut_path}"); '
        f'$sc.TargetPath = "pythonw.exe"; '
        f'$sc.Arguments = \'"{script}"\'; '
        f'$sc.WorkingDirectory = "{script.parent}"; '
        f'$sc.IconLocation = "{icon}"; '
        f'$sc.Description = "Claude Code Auth Switcher"; '
        f'$sc.Save()'
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)


class SetupScreen(Screen):
    CSS = """
    SetupScreen { align: center middle; }
    #box { width: 100%; height: auto; border: solid $primary; padding: 2 4; }
    Label { margin-bottom: 1; }
    Input { margin-bottom: 1; }
    Button { width: 100%; margin-top: 1; }
    """

    def __init__(self, is_edit: bool = False) -> None:
        super().__init__()
        self.is_edit = is_edit

    def compose(self) -> ComposeResult:
        key = load_config().get("api_key", "")
        heading = "Edit API Key" if self.is_edit else "First-time setup — enter API Key"
        with Center():
            with Vertical(id="box"):
                yield Label(heading)
                yield Input(value=key, placeholder="sk-ant-...", password=True, id="key_input")
                yield Button("Save", variant="primary", id="save")
                if self.is_edit:
                    yield Button("Cancel", id="cancel")
                yield Button("Create Desktop Shortcut", id="shortcut")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "shortcut":
            create_desktop_shortcut()
            self.notify("Desktop shortcut created", timeout=4)
            return
        if event.button.id == "cancel":
            self.app.pop_screen()
            return
        key = self.query_one("#key_input", Input).value.strip()
        if not key:
            self.notify("API Key cannot be empty", severity="error")
            return
        cfg = load_config()
        cfg["api_key"] = key
        save_config(cfg)
        self.notify("Saved")
        if self.is_edit:
            self.app.pop_screen()
        else:
            self.app.switch_screen(MainScreen())


_CODE_MSG = {
    0:   "API: No key configured",
    200: "API: ✓ Active",
    401: "API: ✗ 401 — key invalid or revoked",
    402: "API: ✗ 402 — payment / credit issue",
    403: "API: ✗ 403 — key lacks resource access",
    429: "API: ✗ 429 — rate limit / quota exceeded",
    529: "API: ✗ 529 — Anthropic servers overloaded",
    -1:  "API: ✗ Network error",
}


class MainScreen(Screen):
    CSS = """
    MainScreen { align: center middle; }
    #box { width: 100%; height: auto; border: solid $primary; padding: 2 4; }
    #status { text-align: center; margin-bottom: 1; }
    #api_status { text-align: center; margin-bottom: 1; color: $text-muted; }
    #buttons, #buttons2 { height: auto; margin-bottom: 1; }
    #buttons Button, #buttons2 Button { width: 1fr; margin: 0 1; }
    #buttons Button:first-child, #buttons2 Button:first-child { margin-left: 0; }
    #buttons Button:last-child, #buttons2 Button:last-child  { margin-right: 0; }
    #grand_total { margin-top: 1; margin-bottom: 0; }
    DataTable { height: 7; margin-top: 0; }
    """

    def compose(self) -> ComposeResult:
        mode = get_current_mode()
        status = "Mode: API Key (pay-per-use)" if mode == "api" else "Mode: Subscription / OAuth"
        with Center():
            with Vertical(id="box"):
                yield Static(status, id="status")
                yield Static("API: —", id="api_status")
                with Horizontal(id="buttons"):
                    yield Button("Edit Key", id="edit")
                    yield Button("Login", variant="success", id="login")
                    yield Button("Logout", variant="error", id="logout")
                with Horizontal(id="buttons2"):
                    yield Button("Session Log", id="session_log")
                    yield Button("API Health", variant="warning", id="check_api")
                yield Static("", id="grand_total")
                yield DataTable(id="table", cursor_type="row")

    def on_mount(self) -> None:
        self._refresh_table()
        self._last_mtime: float = HISTORY_FILE.stat().st_mtime if HISTORY_FILE.exists() else 0.0
        self.set_interval(1, self._check_history_mtime)
        asyncio.ensure_future(self._do_api_check())

    def _check_history_mtime(self) -> None:
        mtime = HISTORY_FILE.stat().st_mtime if HISTORY_FILE.exists() else 0.0
        if mtime != self._last_mtime:
            self._last_mtime = mtime
            self._refresh_table()

    def _refresh_table(self) -> None:
        table = self.query_one("#table", DataTable)
        table.clear(columns=True)
        table.add_columns("Session", "Model", "In", "Out", "Cost")

        history = load_history()
        grand_total = 0.0
        for entry in reversed(history):
            for model, u in entry.get("models", {}).items():
                cost = u.get("cost", 0)
                grand_total += cost
                short = model.replace("claude-", "")
                table.add_row(
                    entry["ts"],
                    short,
                    f"{u['input_tokens']:,}",
                    f"{u['output_tokens']:,}",
                    f"${cost:.4f}",
                )

        n = len(history)
        self.query_one("#grand_total", Static).update(
            f"Total  {n} session{'s' if n != 1 else ''}  ${grand_total:.4f}"
        )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "edit":
            self.app.push_screen(SetupScreen(is_edit=True))
        elif bid == "login":
            key = load_config().get("api_key", "")
            if not key:
                self.notify("No API Key found — please edit first", severity="error")
                return
            if get_current_mode() == "api":
                self.notify("Already in API Key mode", severity="warning")
                return
            set_api_key(key)
            kill_claude()
            _inject_claude_md(find_claude_cli())
            self.query_one("#status", Static).update("Mode: API Key (pay-per-use)")
            self.notify("API Key active — Claude CLI will use pay-per-use billing", timeout=8)
            asyncio.ensure_future(self._do_api_check())
        elif bid == "logout":
            if get_current_mode() == "oauth":
                self.notify("Already in Subscription mode", severity="warning")
                return
            delete_api_key()
            kill_claude()
            _remove_claude_md()
            self.query_one("#status", Static).update("Mode: Subscription / OAuth")
            self.notify("Switched to Subscription — Claude CLI will use OAuth billing", timeout=8)
        elif bid == "session_log":
            self._refresh_table()
        elif bid == "check_api":
            asyncio.ensure_future(self._do_api_check())

    async def _do_api_check(self) -> None:
        self.query_one("#api_status", Static).update("API: probing…")
        code = await asyncio.to_thread(_probe_api)
        self._update_api_status(code)

    def _update_api_status(self, code: int) -> None:
        self.query_one("#api_status", Static).update(_CODE_MSG.get(code, f"✗ {code} — unknown error"))


class ClaudeSwitcher(App):
    TITLE = "Claude Code Auth Switcher"
    BINDINGS = [("q", "quit", "Quit")]

    def on_mount(self) -> None:
        if load_config().get("api_key"):
            self.push_screen(MainScreen())
        else:
            self.push_screen(SetupScreen())


def _resize_console(cols: int, lines: int) -> None:
    """Resize the Windows console via Win32 API before Textual takes over."""
    try:
        k32 = ctypes.windll.kernel32
        stdout = k32.GetStdHandle(-11)

        class SMALL_RECT(ctypes.Structure):
            _fields_ = [("Left", ctypes.c_short), ("Top", ctypes.c_short),
                        ("Right", ctypes.c_short), ("Bottom", ctypes.c_short)]

        class COORD(ctypes.Structure):
            _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]

        rect = SMALL_RECT(0, 0, cols - 1, lines - 1)
        coord = COORD(cols, lines)
        k32.SetConsoleWindowInfo(stdout, True, ctypes.byref(rect))
        k32.SetConsoleScreenBufferSize(stdout, coord)
        k32.SetConsoleWindowInfo(stdout, True, ctypes.byref(rect))
    except Exception:
        pass


if __name__ == "__main__":
    _resize_console(72, 24)
    ClaudeSwitcher().run()
