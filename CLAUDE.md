# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`mathtools` manages AI coding-agent environments on the developer's machine through a **web dashboard**: a FastAPI backend in [src/web/](src/web/) and a React + Vite frontend in [src/frontend/](src/frontend/). [main.py](src/main.py) only starts the server. There used to be a terminal UI (`--cli`: Rich/questionary installer, Obsidian memory manager, TUI monitor); it has been removed, and only the installer's non-interactive core survives, in [web/installer.py](src/web/installer.py).

The user-facing content it installs (agents, commands, rules, skills, workflows) lives in *other* repos — see `REPOSITORIES` in [repositories.py](src/constants/repositories.py). This repo is only the delivery/observability layer.

## Commands

```bash
# Dev setup (install.sh does this against ~/.local/share/mathtools for end users)
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# Run it (entry point is main:main)
mathtools                       # serve the web dashboard
python src/main.py              # direct; note src/ must be on PYTHONPATH

# Tests (pytest config in pyproject.toml sets testpaths=tests, pythonpath=src)
pytest
pytest tests/test_web_installer.py                          # one file
pytest tests/test_web_sessions.py::test_session_detail_and_messages   # one test
pytest -k harness                                           # by name

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

The project uses a src-layout with `pythonpath = ["src"]`, so **imports are rooted at `src/`, not at a package name**: `from constants.general import VERSION`, `from web.installer import extract_environment`. Never write `from src.web...`. Tests rely on [tests/conftest.py](tests/conftest.py) inserting `src/` into `sys.path` for direct runs.

## Installer architecture

The installer is a matrix of two data tables and no per-environment code:

- `ENVIRONMENTS` ([environments.py](src/constants/environments.py)) — one entry per target agent (`gemini`, `agents`/Antigravity, `opencode`, `claude`). Each has `target_dir` (local dot-folder), `global_dir` (used only for *detection*), and `sources`: a list of 4-tuples `(repo_name, src_path_in_zip, dest_subpath, global_path)`.
- `REPOSITORIES` ([repositories.py](src/constants/repositories.py)) — GitHub archive URL plus the `prefix` GitHub prepends inside the zip.

[web/installer.py](src/web/installer.py) is plain functions with no prompting or printing. `download_repo_zips()` fetches each repo's zip **entirely into memory** (`dict[str, bytes]`) once; those bytes serve both listing available items (`get_available_items`) and writing them (`extract_environment`). Extraction filters zip members by `prefix + src_path`, and per source the selection is either `"all"` or a list of top-level item names. The mode (`local` vs `global`) decides whether files land under `<cwd>/<target_dir>/<dest_subpath>` or under the expanded `global_path` — the two branches produce *different* directory shapes, which is why `sources` carries both. `get_existing_folders` reports what an install would overwrite. Nothing calls these from a route yet: the harness install endpoint is still a simulation (see below).

To add a new agent environment, add an `ENVIRONMENTS` entry; no installer code should need to change.

## Session adapter contract

Session readers live in [src/web/sources/](src/web/sources/) (only [claude.py](src/web/sources/claude.py) so far). Each returns `(list[dict], totals)` where `totals` has exactly the keys `input`/`output`/`cacheR`/`cacheW`, and each session dict carries the full key set: `AI` (2-letter tag), `Project`, `SessionId`, `Summary`, `Model`, `Status` (`"Work"`/`"Wait"`), `TurnCount`, `LastContext`, `ContextWindow`, `TotalTokens`, `InputTokens`, `OutputTokens`, `CacheR`, `CacheW`, `mtime` (epoch seconds — the sort key, so normalize ms timestamps), `Subagents`, `PIDs`, `ProjectPath`, and optionally `Quota`/`Children`. Prefer completing the contract over adding `.get()` fallbacks downstream.

`Status` is derived heuristically from file mtime recency, not from any real process state. Context-window sizes come from `MODEL_CONTEXT_WINDOW` in [source_files.py](src/constants/source_files.py), which also centralizes the other tools' state paths.

**Broad exception swallowing in the sources is deliberate**, not sloppiness: they read other tools' private, undocumented state directories that may be absent, half-written, or schema-changed at any moment. Parsers return empty results instead of failing the request. Keep new parsing code equally defensive.

## Web dashboard architecture

Providers are declared in `AGENT_PROVIDERS` ([web.py](src/constants/web.py)) — Claude Code, Opencode and Codex. A provider can carry `enabled: False` to render as "coming soon" without hardcoding a list. Antigravity is deliberately out of scope.

**Backend layout — routers, Express-style.** [server.py](src/web/server.py) only builds the `FastAPI` app and wires resources together; it holds no route logic. Each resource is a class under [routes/](src/web/routes/) that registers its own endpoints in `__init__` via `router.add_api_route(...)` and implements each one as a method (`HealthRouter`, `AgentsRouter`, `ProjectsRouter`, `SessionsRouter`), then `create_app()` mounts every `.router` with `app.include_router(..., prefix="/api")`. Adding a resource means adding a file under `routes/` and one line in `create_app()` — no edit to any existing router.

Data access for every router runs through one `DataStore` instance ([data.py](src/web/data.py)), constructor-injected so it is trivial to swap or mock as a unit. Its `load_*` methods are the seams:

- `load_agent_sessions(project, agent)` — the single source of session data for every route, in the *session adapter contract* described above, scoped to one project's path and one agent id. `project_sessions(project)` concatenates every enabled agent; `all_sessions()` does that for every registered project (the `/agents` metrics). Claude Code is live via `get_claude_sessions()` → [sources/claude.py](src/web/sources/claude.py); Opencode and Codex return nothing yet. That reader deliberately does not depend on `sessions-index.json` or the PID registry for identity: current Claude Code writes no `sessions-index.json`, `~/.claude/sessions/` is keyed by PID rather than session id, and an assistant message is stored as one record per content block each repeating the full `usage` — so it takes `ProjectPath` from each record's `cwd`, dedupes usage by `message.id`, and caches parsed transcripts on `(mtime, size)` so the live stream's 1s tick only re-reads changed files.
- `load_repositories()` — the projects registered in the SQLite DB ([db/](src/web/db/)), each enriched with live git state by `get_repo_info()`. A separate seam because the session contract only carries a `ProjectPath`; `get_projects()` joins the two on that path.
- `find_project(id)` dedupes the "look up a project or 404" pattern that three routes in `ProjectsRouter` share.

**Path resolution is load-bearing.** `repo_root()` in [paths.py](src/web/paths.py) walks up to the `pyproject.toml` rather than using a fixed `parents[N]`, because the package has already moved once (`src/cli/web` → `src/web`) and a hardcoded depth breaks silently: every `/api/*` route keeps working while the frontend mount disappears. `test_repo_root_is_the_directory_holding_pyproject` fails loudly if that ever regresses. The SPA-fallback `StaticFiles` subclass lives in [spa.py](src/web/spa.py) for the same reason serializers and routers get their own files — one seam per file.

**Domain shape.** Projects (git repos) are the top-level entity and the app's entry point — `/` redirects to `/projects`, and there is no dashboard or cross-project sessions view. A session is only ever reached through its project. A project detail page has three route-backed tabs (`/projects/:projectId/:tab`):

- **Overview** (index) — repository state and headline metrics. Everything that used to sit above the tabs lives here, so the other two tabs get the full viewport height.
- **Sessions** — grouped by the provider that ran them. Cards carry metrics only; **`Open` reveals a full-width `SessionWindow`** at `/projects/:projectId/sessions/:sessionId`, and the `X` returns to the list. It is master/detail: the list is not rendered while a session is open. The window renders *inside* the content area rather than as an overlay, so the sidebar and the project tabs stay usable — that is deliberate, not a styling detail. Its own tabs are local state: **Agent** is a chat that drives the session (Claude Code only so far — see below), Interactions is still a placeholder; only the open session is route-backed, so it survives a reload and can be linked to. An unknown `:sessionId` falls back to the plain list instead of erroring.
- **Harness** — what the installer has deployed into that repo.

**Driving a session.** `POST /api/projects/{id}/agents/claude/sessions/{sid}/prompt` runs one headless turn — `claude -p --resume <sid> --output-format stream-json --include-partial-messages --permission-prompts none` in the session's `ProjectPath`, prompt over stdin — and streams it back as NDJSON. [runners/claude.py](src/web/runners/claude.py) reduces the CLI's events to a small UI vocabulary (`start`/`text`/`tool`/`tool_result`/`done`/`error`) in `translate_event`; `AgentChat.jsx` folds them into turns. Nothing can stop to ask for approval headlessly, so the permission mode picked in the UI decides everything and `bypassPermissions` is refused server-side. One turn per session at a time (409 otherwise); a dropped connection kills the process.

`summarize_sessions()` in [serializers.py](src/web/serializers.py) computes the headline metrics (active sessions, tokens, projects, quota) and is called for four scopes — the whole dashboard, one project, one agent provider, one provider *within* a project — so they all report the same numbers the same way. The frontend mirrors this with a single `StatRow` component.

**Providers report different things, and the difference is meaningful.** A metric a provider does not expose is `None`, never `0`: Codex reports no cache usage and no turn count, so the UI shows "—" rather than a zero a reader would take as real. Aggregation coerces with `or 0`; per-session values pass `None` through untouched. `test_unreported_metrics_stay_none_rather_than_zero` pins this.

**Harness.** `serialize_harness()` derives each provider's installable component types from the installer's own `ENVIRONMENTS` source tuples rather than a second hardcoded list, so a provider gains a component type in the web UI the moment the installer learns it. `AGENT_PROVIDERS[*]["env"]` is the key into `ENVIRONMENTS`; `None` (Codex) means the provider can have sessions but nothing the installer knows how to deploy. **The install/update endpoint is a simulation** — it returns what it would write and touches nothing, and the UI says so explicitly. Wiring it up means calling `download_repo_zips()` + `extract_environment()` from [web/installer.py](src/web/installer.py) with the chosen environment, scope and components.

[serializers.py](src/web/serializers.py) is the only place that knows both vocabularies: it maps the adapters' PascalCase dicts to the camelCase JSON the frontend consumes (`SessionId` → `id`, `LastContext`/`ContextWindow` → a computed `context.pct`, …). Keep new key mappings there rather than teaching the frontend about adapter key names.

**Serving.** In development, Vite runs on :5173 and proxies `/api` to uvicorn on :8765 (`DEV_ORIGINS` also whitelists it for CORS). In production FastAPI serves `src/frontend/dist/` from the same origin, so the API client uses a relative `/api` base in both modes.

Two coupled details keep deep links working, and breaking either one produces a *blank page with no error*:

- Vite's `base` must stay `'/'`. With a relative base, `/projects/mathtools` requests `./assets/x.js` as `/projects/assets/x.js`.
- The static mount is a `StaticFiles` subclass that falls back to `index.html` on 404, since BrowserRouter paths have no file on disk — but it only does so for paths whose last segment has no `.`. Falling back for asset requests too would answer a `.js` request with HTML and a 200.

**Live updates (SSE).** Reads are REST, and `GET /api/events` keeps them current. One `EventHub` ([events.py](src/web/events.py)) per app, shared by every connected tab, runs `DataStore.live_snapshot()` in a worker thread every `LIVE_INTERVAL_SECONDS` (1s) while at least one client is connected, diffs it by key against the previous snapshot and pushes only what changed. The events are `projects`, `agents` and `project` (one per changed project), and **their payloads are the exact REST bodies**: `live_snapshot()` and the routes share `project_detail()`/`agents_overview()`, and `test_live_snapshot_payloads_equal_the_rest_bodies` pins that. A new connection is first sent the whole current snapshot, so a reconnect resyncs with no refetch. The polling did not go away, it moved server-side and happens once instead of per tab per view; what makes a 1s tick cheap is the transcript cache plus `DataStore._git_state`, which caches each repo's five git calls until a file in `.git` changes (`HEAD`, `index`, `FETCH_HEAD`, `ORIG_HEAD`) or `GIT_REFRESH_SECONDS` (5s) pass — plain working-tree edits touch nothing git-owned, so only the timer catches those. An SSE response never ends by itself: `MathToolsServer` runs a `uvicorn.Server` subclass whose `handle_exit` calls `EventHub.close()`, which ends every stream so Ctrl+C exits at once instead of sitting out `timeout_graceful_shutdown` and dumping a cancellation traceback. Mutations (create project, harness install, agent prompt) stay plain POSTs.

**Frontend.** `App.jsx` owns the single live query of `/api/projects` and passes the result down; the sidebar (project badge and, in its footer, the active-session count) and the Projects grid all read from it — there is no topbar, so switching views never refetches. Sessions have no flat API: they are nested as `/api/projects/{id}/agents/{agent}/sessions/{session}[/messages]` (`SessionsRouter`), and `GET /api/projects/{id}` inlines the same per-agent grouping under `agents`. `DataStore.project_sessions()` is the only place the session→project join (on `ProjectPath`) is made. The SPA fallback never answers `/api/*`, so a removed endpoint 404s instead of returning `index.html`. `api.js` stays a complete mirror of the API surface, so wiring the SessionWindow's Interactions tab up to `sessionMessages` needs no backend work.

Views that show changing state use `useLiveApi(fetcher, { event, key, accept })` ([useLiveApi.js](src/frontend/src/hooks/useLiveApi.js)): one REST load, then each matching event from the shared `EventSource` in [live.js](src/frontend/src/api/live.js) replaces the data (`accept` filters, e.g. `p.id === projectId` for `project` events). `live.js` opens the connection with the first subscriber, closes it with the last, and retries after a hard failure. `useApi` stays for one-off reads (Harness). Its `replace()` is how pushed data lands, and it bumps a version counter so a fetch already in flight — including one for the previous `key` — is discarded instead of overwriting newer state.

`useApi` keeps the last good payload when a refresh fails — only a failed *first* load shows an error state. It holds the fetcher in a ref, so **passing an inline arrow is safe**; refetching on a changed argument is opted into with `key` (`key: projectId`). This matters: an earlier version keyed the effect on the fetcher's identity, and an inline arrow there re-ran the effect every render, which reset `loading` to true forever and left the view stuck on a spinner. `SessionTable` takes a `compact` prop that drops the Model and Turns columns for the narrow dashboard column; the table is `table-layout: fixed` with explicit `<th>` widths, which is what makes truncation work — under auto layout a long summary stretches the table past its container.

## Testing conventions

Tests mirror the source tree (`tests/test_<module_path>.py`) and never touch the network or the real home directory. [conftest.py](tests/conftest.py) provides:

- `framework_zip`/`skills_zip` — in-memory zips with the exact GitHub prefixes, so installer extraction runs end to end.
- `web_client` — a `TestClient` with `mathtools` and `dotfiles` registered as real `git init`ed repos under `tmp_path`, with `DataStore.load_agent_sessions`/`load_harness` patched to serve [mock_data.py](src/web/mock_data.py) re-homed onto those paths. Use it for any route that needs projects with sessions; a bare `create_app(db_path=tmp_path / ...)` client has no projects.
- `tmp_dir` — chdir isolation.

Session readers are tested against transcripts written under `tmp_path` and passed as `base_dir=`; the agent runner is tested against a fake `claude` script. The SSE stream is tested at the `EventHub` level (diffing, fan-out, `stream()` driven with `__anext__`/`aclose()`), not through `TestClient`, which buffers a whole response and would hang on an endless one; `app.state.data_store`/`app.state.event_hub` expose the instances the routes use.
