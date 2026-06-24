# Claude Switcher Project Rules

## Project Context
- **Name**: Claude_Switcher
- **GitHub Repository**: https://github.com/liewcc/Claude_Switcher (public)
- **Primary Function**: Windows TUI tool to switch Claude Code between API Key mode and Subscription/OAuth mode, with session usage tracking.

## Tool & Environment Info
- **Claude Code CLI**: Located at `C:\Users\cclie\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude-code\2.1.181\claude.exe` (added to user PATH). Can be executed as `claude` from the shell.
- **Verification Command**: Use `claude -p "prompt"` for non-interactive prompts.
- **gemi MCP Server**: Fully operational for UI and model interactions.

## Version Control Guidelines
- The default branch is `main`.
- Always ignore local configurations and logs: `config.json`, `usage_history.json`, `usage_latest.json`, `hook_dump.jsonl`, `.claude/`.
