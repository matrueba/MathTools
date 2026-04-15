# ── Environment Definitions ─────────────────────────────────────────────────
# Each environment maps to:
#   target_dir  → the dot-folder that will be created in the user's project
#   sources     → list of (src_path_in_zip, dest_subpath) tuples
#                 src_path_in_zip is relative to the ZIP root
#                 dest_subpath is relative to target_dir
#
# Shared content (skills) lives under .agents/skills and .gemini/skills in the
# repo (they are identical).  We always pull from .agents/skills as canonical
# source and place it where each environment expects it.


ENVIRONMENTS = {
    "gemini": {
        "label": "Gemini CLI",
        "description": "Google Gemini CLI (.gemini) – supports agents, commands & skills",
        "target_dir": ".gemini",
        "global_dir": "~/.gemini",
        "sources": [
            ("framework", "src/agents", "agents", "~/.gemini/agents"),
            ("framework", "src/commands", "commands", "~/.gemini/commands"),
            ("skills", "skills", "skills", "~/.gemini/skills"),
        ],
    },
    "agents": {
        "label": "Standard IDE agents",
        "description": "IDE agents (VSCode / AntiGravity / Cursor) (.agents) – supports rules, skills & workflows",
        "target_dir": ".agents",
        "global_dir": "~/.agents",
        "sources": [
            ("framework", "src/rules", "rules", "~/.agents/rules"),
            ("skills", "skills", "skills", "~/.agents/skills"),
            ("framework", "src/workflow", "workflows", "~/.agents/workflows"),
        ],
    },
    "opencode": {
        "label": "Opencode",
        "description": "Opencode CLI (.opencode) – supports agents, commands & skills",
        "target_dir": ".opencode",
        "global_dir": "~/.config/opencode",
        "sources": [
            # Opencode shares the same agent/command model as Gemini CLI
            ("framework", "src/agents", "agents", "~/.config/opencode/agents"),
            ("framework", "src/commands", "commands", "~/.config/opencode/commands"),
            ("skills", "skills", "skills", "~/.config/opencode/skills"),
        ],
    },
    "claude": {
        "label": "Claude Code",
        "description": "Claude Code (.claude) – supports agents, commands & skills",
        "target_dir": ".claude",
        "global_dir": "~/.claude",
        "sources": [
            ("framework", "src/agents", "agents", "~/.claude/agents"),
            ("framework", "src/commands", "commands", "~/.claude/commands"),
            ("skills", "skills", "skills", "~/.claude/skills"),
        ],
    },
}
