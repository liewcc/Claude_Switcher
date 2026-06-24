# Claude Switcher — Handoff

## What was built
A Windows TUI tool (`run.bat` → `app.py`) for switching Claude Code between API Key mode and Subscription/OAuth mode, with session usage tracking.

## Current state — everything is working

### API Key mode is ACTIVE
- `ANTHROPIC_API_KEY` is written to `~/.claude/settings.json` under `"env"` key
- Also written to `HKCU\Environment` registry (for CLI in terminal)
- `~/.claude/CLAUDE.md` has been injected with CLI spawning instructions (via Login button)

### How CLI spawning works
- Claude desktop app conversations always use OAuth (blue circle) — unavoidable by design
- For coding tasks: Claude (in app) spawns `claude.exe -p "prompt"` as subprocess → uses API key → pay-per-use billing
- CLI path (cached in `config.json`): `C:\Users\cclie\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude-code\2.1.181\claude.exe`
- `ANTHROPIC_API_KEY` is visible in Bash subprocesses (confirmed via test)
- CLI responded correctly in headless `-p` mode (confirmed via test)

### Key files
| File | Purpose |
|------|---------|
| `D:\AI\Claude_Switcher\app.py` | Main TUI app |
| `D:\AI\Claude_Switcher\run.bat` | Launcher |
| `D:\AI\Claude_Switcher\config.json` | Stores `api_key` + `cli_path` |
| `D:\AI\Claude_Switcher\usage_history.json` | Session usage log |
| `D:\AI\Claude_Switcher\usage_summary.py` | Stop hook handler |
| `~/.claude/settings.json` | Has `env.ANTHROPIC_API_KEY` + Stop hook + MCP servers |
| `~/.claude/CLAUDE.md` | Has injected CLI spawning instructions (Login wrote this) |

### Switcher button behaviour
- **Login**: writes key to `settings.json` + registry, injects section into `CLAUDE.md`, kills Claude
- **Logout**: removes key from `settings.json` + registry, removes section from `CLAUDE.md`, kills Claude
- **Edit Key**: opens key input screen

## What to verify in new conversation
1. Open new conversation in Claude desktop app
2. Ask Claude: "请根据 CLAUDE.md 的指示，用 CLI 执行一个简单任务，例如 echo hello，确认 API key 模式是否生效"
3. Claude should use `claude.exe -p "..."` via PowerShell tool without being told the path
4. Check `usage_history.json` after a session to confirm Stop hook is recording usage

## Known limitations
- Blue circle (subscription quota) will always decrease for the app conversation itself — by design (OAuth)
- `claude remote-control` requires OAuth — not relevant to this setup
- CLI path contains version number (`2.1.181`) — `find_claude_cli()` in `app.py` will auto-update via glob if version changes

## Pending / nice-to-have
- Visually confirm the DataTable layout in Switcher TUI (3 buttons in a row + scrollable history table)
- Run `run.bat` and take a screenshot to confirm UI looks correct
