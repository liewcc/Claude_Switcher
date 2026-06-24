# Claude Code Auth Switcher

A minimal TUI tool for switching Claude Code between **API Key mode** (pay-per-use) and **Subscription / OAuth mode** on Windows.

## Requirements

- Windows 10/11
- Python 3.10+
- Claude Code desktop app installed

## Setup

Run once before first use:

```
setup.bat
```

## Usage

```
run.bat
```

**First launch** — enter your Anthropic API Key and save it.  
**Subsequent launches** — choose an action:

| Button | Effect |
|--------|--------|
| Edit API Key | Update the stored key |
| Login (API Key mode) | Set key → restart Claude in pay-per-use mode |
| Logout (Subscription mode) | Remove key → restart Claude in OAuth mode |

The API Key is stored locally in `config.json` (excluded from git). See `config.example.json` for the expected format.  
Press `q` to quit without changing anything.

## How it works

- **Login** — writes `ANTHROPIC_API_KEY` to the Windows user environment via `setx`, then restarts Claude Code.  
- **Logout** — removes the variable from the registry via `REG DELETE`, then restarts Claude Code.  
- Environment changes take effect in the new Claude process immediately.
