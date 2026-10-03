# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`mathtools` manages AI coding-agent environments on the developer's machine. It has two front ends, chosen by a flag in [main.py](src/main.py) — **`mathtools` serves the web dashboard** (FastAPI + React) and **`mathtools --cli` opens the terminal UI** (Rich + questionary), which carries the **framework installer**, the **Obsidian memory manager** and the **live TUI monitoring dashboard**. Each is a manager class instantiated inside `run_cli()`.

The two modes are mutually exclusive by design: the web dashboard is not reachable from the CLI menu, and `run_web()` skips environment detection entirely. `main(argv=None)` takes its argument list as a parameter so tests can pick a mode without patching `sys.argv`.

The user-facing content it installs (agents, commands, rules, skills, workflows) lives in *other* repos — see `REPOSITORIES` in [repositories.py](src/constants/repositories.py). This repo is only the delivery/observability layer.

## Commands

```bash
# Dev setup (install.sh does this against ~/.local/share/mathtools for end users)
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# Run it (entry point is main:main)
mathtools                       # web dashboard — the default
mathtools --cli                 # interactive terminal UI instead
python src/main.py --cli        # direct; note src/ must be on PYTHONPATH

# Tests (pytest config in pyproject.toml sets testpaths=tests, pythonpath=src)
pytest
pytest tests/test_cli_installer.py                          # one file
pytest tests/test_cli_monitoring.py::test_claude_source_parse_no_dir   # one test
pytest -k monitoring                                        # by name

# Coverage (configured to fail under 80%; the repo currently sits well below
# that, and CI does not run it — `pytest tests/` has no --cov flag)
pytest --cov --cov-report=term-missing
```

Web dashboard (see the section below):

```bash
cd src/frontend
npm install
npm run dev      # Vite on :5173, proxies /api to uvicorn on :8765
npm run build    # emits src/frontend/dist/, which FastAPI then serves

# Backend on its own (mock data)
PYTHONPATH=src uvicorn web.server:app --port 8765
```

`pytest` needs `httpx` installed for the FastAPI `TestClient` used by
[test_web.py](tests/test_web.py).

CI ([.github/workflows/tests.yml](.github/workflows/tests.yml)) runs `pytest tests/` on Python 3.10/3.11/3.12 for push/PR to `main`. There is no linter or formatter configured.

Work happens on `develop`; `main` is what `install.sh` clones for end users, so releases merge there.

## Import convention

The project uses a src-layout with `pythonpath = ["src"]`, so **imports are rooted at `src/`, not at a package name**: `from constants.general import VERSION`, `from cli.installer import FrameworkInstaller`. Never write `from src.cli...`. Tests rely on [tests/conftest.py](tests/conftest.py) inserting `src/` into `sys.path` for direct runs.

## Installer architecture

The installer is a matrix of two data tables and no per-environment code:

- `ENVIRONMENTS` ([environments.py](src/constants/environments.py)) — one entry per target agent (`gemini`, `agents`/Antigravity, `opencode`, `claude`). Each has `target_dir` (local dot-folder), `global_dir` (used only for *detection*), and `sources`: a list of 4-tuples `(repo_name, src_path_in_zip, dest_subpath, global_path)`.
- `REPOSITORIES` ([repositories.py](src/constants/repositories.py)) — GitHub archive URL plus the `prefix` GitHub prepends inside the zip.

[FrameworkInstaller](src/cli/installer.py) downloads each repo's zip **entirely into memory** (`dict[str, bytes]`) once, then reuses those bytes for both listing available items (`get_available_items`) and extraction (`extract_environment`). Extraction filters zip members by `prefix + src_path`, and per-source the user's selection is either the string `"all"` or a list of top-level item names. The chosen mode (`local` vs `global`, per environment) decides whether files land under `cwd/<target_dir>/<dest_subpath>` or under the expanded `global_path` — note the two branches produce *different* directory shapes, which is why `sources` carries both.

To add a new agent environment, add an `ENVIRONMENTS` entry; no installer code should need to change.

## Monitoring architecture

[MonitoringManager](src/cli/monitoring/monitoring.py) is a pure aggregator over pluggable **source adapters**, one file per agent tool:

| Source | State it reads | Format |
| --- | --- | --- |
| [claude_source.py](src/cli/monitoring/claude_source.py) | `~/.claude/projects/*/sessions-index.json` → per-session `.jsonl`, plus `~/.claude/sessions/<id>.json` for real PID/cwd | JSONL transcripts |
| [opencode_source.py](src/cli/monitoring/opencode_source.py) | `~/.local/share/opencode/opencode.db` (`session`, `message` tables), opened read-only via `file:...?mode=ro` so it never blocks the live app | SQLite |
| [gemini_source.py](src/cli/monitoring/gemini_source.py) | `~/.gemini/tmp/<project>/chats/session-*.json` | JSON |
| [antigravity_source.py](src/cli/monitoring/antigravity_source.py) | `~/.gemini/antigravity/conversations/*.pb` + `brain/` artifacts | opaque protobuf — token counts are **estimated from file size**, not parsed |

All paths are centralized in [source_files.py](src/constants/source_files.py) along with `MODEL_CONTEXT_WINDOW`, which drives the context-saturation bars.

**The adapter contract:** each source exposes `parse_<tool>_sessions() -> (list[dict], totals_dict)` where `totals` has exactly the keys `input`/`output`/`cacheR`/`cacheW`. Session dicts are consumed by both the table in `_build_screen` and the detail pane in [extended.py](src/cli/monitoring/extended.py), so a new source should emit the full key set: `AI` (2-letter tag), `Project`, `SessionId`, `Summary`, `Model`, `Status` (`"Work"`/`"Wait"`), `TurnCount`, `LastContext`, `ContextWindow`, `TotalTokens`, `InputTokens`, `OutputTokens`, `CacheR`, `CacheW`, `mtime` (epoch seconds — used as the global sort key, so normalize ms timestamps), `Subagents`, `PIDs`, `ProjectPath`, and optionally `Quota`/`Children`. Existing sources are inconsistent here (only Claude sets `Quota`/`Children`; Claude omits `CacheR`), which is why renderers use `.get()` with defaults — prefer completing the contract over adding more `.get()` fallbacks.

`Status` is derived heuristically from file mtime recency (30–60s depending on source), not from any real process state. Live PIDs are resolved opportunistically by `pgrep` + `/proc/<pid>/cwd` matching, and per-process CPU/memory in the detail pane comes from shelling out to `ps` — all of this is Linux-specific and degrades to `"?"` rather than failing.

**Broad exception swallowing in the sources is deliberate**, not sloppiness: the dashboard reads other tools' private, undocumented state directories that may be absent, half-written, or schema-changed at any moment. Parsers return empty results instead of crashing the TUI. Keep new parsing code equally defensive.

**TUI loop:** raw terminal input via `termios`/`tty.setcbreak` with non-blocking `select` reads (arrow escape sequences reassembled in `_read_key`), rendered by `rich.Live` with `auto_refresh=False` — the screen is rebuilt only on keypress or the 3-second data refresh. The original termios settings are restored in a `finally` block; any change to the loop must preserve that or it will leave the user's terminal broken.

## Web dashboard architecture

A second surface over the same domain, deliberately kept out of `src/cli/`: FastAPI backend in [src/web/](src/web/), React + Vite frontend in [src/frontend/](src/frontend/). Providers are declared in `AGENT_PROVIDERS` ([web.py](src/constants/web.py)) — Claude Code, Opencode and Codex are `enabled`, Gemini carries `enabled: False` so the UI renders it as "coming soon" without hardcoding a list. Antigravity is deliberately out of scope.

**Backend layout — routers, Express-style.** [server.py](src/web/server.py) only builds the `FastAPI` app and wires resources together; it holds no route logic. Each resource is a class under [routes/](src/web/routes/) that registers its own endpoints in `__init__` via `router.add_api_route(...)` and implements each one as a method (`HealthRouter`, `AgentsRouter`, `ProjectsRouter`, `SessionsRouter`), then `create_app()` mounts every `.router` with `app.include_router(..., prefix="/api")`. Adding a resource means adding a file under `routes/` and one line in `create_app()` — no edit to any existing router.

Data access for every router runs through one `DataStore` instance ([data.py](src/web/data.py)), constructor-injected so it is trivial to swap or mock as a unit. Its `load_*` methods are the seams:

- `load_sessions()` — the single source of session data for every route. It emits dicts in the *exact monitoring-adapter contract* described above, so going live means swapping that one method body for `ClaudeSource().parse_claude_sessions()`. `test_mock_sessions_follow_the_monitoring_contract` guards the property.
- `load_repositories()` — git metadata per project. This is a separate seam because the monitoring contract only carries a `ProjectPath`; `build_projects()` joins the two on that path. The real version will shell out to git in each `ProjectPath`.
- `find_project(id)` dedupes the "look up a project or 404" pattern that three routes in `ProjectsRouter` share.

**Path resolution is load-bearing.** `repo_root()` in [paths.py](src/web/paths.py) walks up to the `pyproject.toml` rather than using a fixed `parents[N]`, because the package has already moved once (`src/cli/web` → `src/web`) and a hardcoded depth breaks silently: every `/api/*` route keeps working while the frontend mount disappears. `server.py` re-exports it as `_repo_root` for backward compatibility. `test_repo_root_is_the_directory_holding_pyproject` fails loudly if that ever regresses. The SPA-fallback `StaticFiles` subclass lives in [spa.py](src/web/spa.py) for the same reason serializers and routers get their own files — one seam per file.

**Domain shape.** Projects (git repos) are the top-level entity and the app's entry point — `/` redirects to `/projects`, and there is no dashboard or cross-project sessions view. A session is only ever reached through its project. A project detail page has three route-backed tabs (`/projects/:projectId/:tab`):

- **Overview** (index) — repository state and headline metrics. Everything that used to sit above the tabs lives here, so the other two tabs get the full viewport height.
- **Sessions** — grouped by the provider that ran them. Cards carry metrics only; **`Open` reveals a full-width `SessionWindow`** at `/projects/:projectId/sessions/:sessionId`, and the `X` returns to the list. It is master/detail: the list is not rendered while a session is open. The window renders *inside* the content area rather than as an overlay, so the sidebar and the project tabs stay usable — that is deliberate, not a styling detail. Its own tabs (Agent, Interactions) are placeholders holding local state; only the open session is route-backed, so it survives a reload and can be linked to. An unknown `:sessionId` falls back to the plain list instead of erroring.
- **Harness** — what the installer has deployed into that repo.

`summarize_sessions()` in [serializers.py](src/web/serializers.py) computes the headline metrics (active sessions, tokens, projects, quota) and is called for four scopes — the whole dashboard, one project, one agent provider, one provider *within* a project — so they all report the same numbers the same way. The frontend mirrors this with a single `StatRow` component.

**Providers report different things, and the difference is meaningful.** A metric a provider does not expose is `None`, never `0`: Codex reports no cache usage and no turn count, so the UI shows "—" rather than a zero a reader would take as real. Aggregation coerces with `or 0`; per-session values pass `None` through untouched. `test_unreported_metrics_stay_none_rather_than_zero` pins this.

**Harness.** `serialize_harness()` derives each provider's installable component types from the installer's own `ENVIRONMENTS` source tuples rather than a second hardcoded list, so a provider gains a component type in the web UI the moment the installer learns it. `AGENT_PROVIDERS[*]["env"]` is the key into `ENVIRONMENTS`; `None` (Codex) means the provider can have sessions but nothing the installer knows how to deploy. **The install/update endpoint is a simulation** — it returns what it would write and touches nothing, and the UI says so explicitly. Wiring it up means calling `FrameworkInstaller` with the chosen environment, scope and components.

[serializers.py](src/web/serializers.py) is the only place that knows both vocabularies: it maps the CLI's PascalCase dicts to the camelCase JSON the frontend consumes (`SessionId` → `id`, `LastContext`/`ContextWindow` → a computed `context.pct`, …). Keep new key mappings there rather than teaching the frontend about CLI names.

**Serving.** In development, Vite runs on :5173 and proxies `/api` to uvicorn on :8765 (`DEV_ORIGINS` also whitelists it for CORS). In production FastAPI serves `src/frontend/dist/` from the same origin, so the API client uses a relative `/api` base in both modes.

Two coupled details keep deep links working, and breaking either one produces a *blank page with no error*:

- Vite's `base` must stay `'/'`. With a relative base, `/projects/mathtools` requests `./assets/x.js` as `/projects/assets/x.js`.
- The static mount is a `StaticFiles` subclass that falls back to `index.html` on 404, since BrowserRouter paths have no file on disk — but it only does so for paths whose last segment has no `.`. Falling back for asset requests too would answer a `.js` request with HTML and a 200.

**Frontend.** `App.jsx` owns a single poll of `/api/projects` (3s, matching the TUI) and passes the result down; the sidebar badge, the topbar's active count and the Projects grid all read from it, so switching views never refetches. `/api/sessions`, `/api/stats` and `/api/sessions/{id}/messages` still exist and are still tested, but no view consumes them today — the dashboard was removed, and the transcript moved out of the session cards ahead of the SessionWindow's Interactions tab. `api.js` stays a complete mirror of the API surface, so wiring that tab up needs no backend work.

`useApi` keeps the last good payload when a refresh fails — only a failed *first* load shows an error state. It holds the fetcher in a ref, so **passing an inline arrow is safe**; refetching on a changed argument is opted into with `key` (`key: projectId`). This matters: an earlier version keyed the effect on the fetcher's identity, and an inline arrow there re-ran the effect every render, which reset `loading` to true forever and left the view stuck on a spinner. `SessionTable` takes a `compact` prop that drops the Model and Turns columns for the narrow dashboard column; the table is `table-layout: fixed` with explicit `<th>` widths, which is what makes truncation work — under auto layout a long summary stretches the table past its container.

## Testing conventions

Tests mirror the source tree (`tests/test_<module_path>.py`) and never touch the network or the real filesystem: [conftest.py](tests/conftest.py) provides `framework_zip`/`skills_zip` fixtures that build in-memory zips with the exact GitHub prefixes so installer extraction can be exercised end to end, plus `tmp_dir` (chdir isolation), `sample_vault`, and `sample_config`. Monitoring tests patch `Path.exists`/`sqlite3` at the source module and assert on the `(sessions, totals)` tuple shape.
