# ── Web Dashboard Configuration ─────────────────────────────────────────────

WEB_HOST = "127.0.0.1"
WEB_PORT = 8765

# Path (relative to the repo root) where Vite writes the production bundle.
FRONTEND_DIST_DIR = "src/frontend/dist"

# Vite dev server, allowed as a CORS origin so `npm run dev` can talk to the API.
DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# ── Supported agent providers ───────────────────────────────────────────────
# `enabled` gates whether the UI lets you drill into the provider.
# `env` is the key into constants.environments.ENVIRONMENTS, which is what the
# installer can deploy into a project — None means the harness tab can show
# that provider's sessions but has nothing to install for it.
#
# Antigravity is intentionally absent: it is monitored by the TUI only.

AGENT_PROVIDERS = [
    {
        "id": "claude",
        "label": "Claude Code",
        "tag": "CL",
        "accent": "#d97757",
        "enabled": True,
        "env": "claude",
    },
    {
        "id": "opencode",
        "label": "Opencode",
        "tag": "OC",
        "accent": "#4ec9b0",
        "enabled": True,
        "env": "opencode",
    },
    {
        "id": "codex",
        "label": "Codex",
        "tag": "CX",
        "accent": "#a1a1aa",
        "enabled": True,
        "env": None,
    },
    {
        "id": "gemini",
        "label": "Gemini CLI",
        "tag": "GE",
        "accent": "#4285f4",
        "enabled": False,
        "env": "gemini",
    },
]

# Component types a harness can contain, in display order. The installer's
# ENVIRONMENTS entries name these in their `sources` tuples.
HARNESS_COMPONENT_TYPES = ["agents", "commands", "skills", "rules", "workflows"]
