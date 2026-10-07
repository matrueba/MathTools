CLAUDE_BASE_DIR = "~/.claude/projects"
OPENCODE_BASE_DIR = "~/.config/opencode"
OPENCODE_DB_PATH = "~/.local/share/opencode/opencode.db"


MODEL_CONTEXT_WINDOW = {
    "claude":{
        "opus-5.5": 1000000,
        "sonnet-5.5": 1000000,
    },
    "opencode": {
        "minimax-m2.5-free": 200000
    },
    "codex": {
    }
}