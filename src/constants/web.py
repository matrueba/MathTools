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
    }
]

# Component types a harness can contain, in display order. The installer's
# ENVIRONMENTS entries name these in their `sources` tuples.
HARNESS_COMPONENT_TYPES = ["agents", "commands", "skills", "rules", "workflows"]

# ── Persistence ─────────────────────────────────────────────────────────────
# SQLite file holding what the user registers through the dashboard (project
# paths, …). Lives under ~/.mathtools so all of mathtools' state is in one
# folder; `create_app(db_path=...)` overrides it, which is what tests use.
DB_PATH = "~/.mathtools/mathtools.db"

# ── Live updates (GET /api/events) ──────────────────────────────────────────
# How often the server re-reads session and git state for the SSE stream.
# Session transcripts are cached on (mtime, size), so a tick that finds
# nothing new costs a directory glob and a stat per file.
LIVE_INTERVAL_SECONDS = 1.0

# Git state is cached per repository and re-read when a git operation touches
# `.git`, or after this long — plain edits to the working tree touch nothing
# git-owned, so only the timer catches them.
GIT_REFRESH_SECONDS = 5.0

# A comment line sent on an idle stream, so proxies do not time it out and a
# vanished client is noticed on the next write.
LIVE_KEEPALIVE_SECONDS = 15.0
