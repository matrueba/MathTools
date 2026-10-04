import pytest

from fastapi.testclient import TestClient

# The 'src' directory is added to sys.path by tests/conftest.py

from web.mock_data import (
    get_mock_chat,
    get_mock_harness,
    get_mock_repositories,
    get_mock_sessions,
)
from web.serializers import (
    serialize_harness,
    serialize_message,
    serialize_project,
    serialize_session,
    serialize_totals,
    summarize_sessions,
)
from web.server import WebDashboard, _repo_root, create_app
from constants.web import AGENT_PROVIDERS, FRONTEND_DIST_DIR, WEB_PORT


@pytest.fixture
def client():
    return TestClient(create_app())


# ── Mock data ───────────────────────────────────────────────────────────────

def test_mock_sessions_return_sessions_and_totals():
    sessions, totals = get_mock_sessions()
    assert sessions
    assert set(totals) == {"input", "output", "cacheR", "cacheW"}


def test_mock_sessions_follow_the_monitoring_contract():
    """Mock data must be swappable with a real monitoring source adapter."""
    required = {
        "AI", "Project", "SessionId", "Summary", "Model", "Status", "TurnCount",
        "LastContext", "ContextWindow", "TotalTokens", "InputTokens",
        "OutputTokens", "CacheR", "CacheW", "mtime", "Subagents", "PIDs",
        "ProjectPath",
    }
    sessions, _ = get_mock_sessions()
    for session in sessions:
        assert required <= set(session), f"missing {required - set(session)}"


def test_mock_totals_match_the_sum_of_sessions():
    # `or 0`: a provider may report a metric as None (not available).
    sessions, totals = get_mock_sessions()
    assert totals["input"] == sum(s["InputTokens"] or 0 for s in sessions)
    assert totals["cacheR"] == sum(s["CacheR"] or 0 for s in sessions)


# ── Serializers ─────────────────────────────────────────────────────────────

def test_serialize_session_maps_to_camel_case():
    session = {
        "SessionId": "abc123", "AI": "CL", "Project": "demo", "Summary": "Do a thing",
        "Model": "claude-opus-4.6", "Status": "Work", "TurnCount": 5,
        "LastContext": 50_000, "ContextWindow": 200_000, "TotalTokens": 1000,
        "InputTokens": 400, "OutputTokens": 100, "CacheR": 500, "CacheW": 0,
        "mtime": 1_700_000_000, "PIDs": [], "Children": [], "Subagents": [],
        "ProjectPath": "/tmp/demo",
    }
    result = serialize_session(session)

    assert result["id"] == "abc123"
    assert result["status"] == "work"
    assert result["context"]["pct"] == 25.0
    assert result["tokens"]["cacheRead"] == 500


def test_serialize_session_tolerates_missing_keys():
    """Sources are inconsistent about optional keys; serializing must not crash."""
    result = serialize_session({"SessionId": "x"})
    assert result["project"] == "Unknown"
    assert result["context"]["pct"] == 0.0
    assert result["summary"] == "No summary"


def test_serialize_session_handles_zero_context_window():
    result = serialize_session({"SessionId": "x", "ContextWindow": 0, "LastContext": 10})
    assert result["context"]["pct"] == 0.0


def test_serialize_totals_counts_active_sessions():
    sessions = [
        {"Status": "Work", "Project": "a", "Quota": None},
        {"Status": "Wait", "Project": "a", "Quota": {"five_hour_pct": 10.0}},
        {"Status": "Wait", "Project": "b", "Quota": None},
    ]
    totals = {"input": 10, "output": 20, "cacheR": 30, "cacheW": 40}
    result = serialize_totals(totals, sessions)

    assert result["sessions"] == {"total": 3, "active": 1, "idle": 2}
    assert result["projects"] == 2
    assert result["tokens"]["total"] == 100
    assert result["quota"] == {"five_hour_pct": 10.0}


def test_serialize_totals_without_quota_data():
    result = serialize_totals(
        {"input": 0, "output": 0, "cacheR": 0, "cacheW": 0},
        [{"Status": "Wait", "Project": "a", "Quota": None}],
    )
    assert result["quota"] is None


# ── API routes ──────────────────────────────────────────────────────────────

def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_agents_endpoint_lists_every_provider(client):
    response = client.get("/api/agents")
    assert response.status_code == 200

    agents = response.json()["agents"]
    assert len(agents) == len(AGENT_PROVIDERS)

    claude = next(a for a in agents if a["id"] == "claude")
    assert claude["enabled"] is True
    assert claude["sessionCount"] > 0

    # Gemini is the remaining "coming soon" provider.
    gemini = next(a for a in agents if a["id"] == "gemini")
    assert gemini["enabled"] is False
    assert gemini["sessionCount"] == 0


def test_agents_endpoint_reports_dashboard_stats_per_provider(client):
    agents = client.get("/api/agents").json()["agents"]

    claude = next(a for a in agents if a["id"] == "claude")
    assert claude["stats"]["sessions"]["total"] == claude["sessionCount"]
    assert claude["stats"]["tokens"]["total"] > 0
    assert claude["stats"]["projects"] > 0

    # A provider with no sessions still reports a zeroed stats block, so the
    # UI can render the same layout for every card.
    gemini = next(a for a in agents if a["id"] == "gemini")
    assert gemini["stats"]["sessions"] == {"total": 0, "active": 0, "idle": 0}
    assert gemini["stats"]["tokens"]["total"] == 0
    assert gemini["stats"]["quota"] is None


def test_stats_endpoint(client):
    body = client.get("/api/stats").json()
    assert body["sessions"]["total"] > 0
    assert body["tokens"]["total"] > 0


def test_sessions_endpoint_is_sorted_by_recency(client):
    sessions = client.get("/api/sessions").json()["sessions"]
    assert len(sessions) > 1

    timestamps = [s["updatedAt"] for s in sessions]
    assert timestamps == sorted(timestamps, reverse=True)


def test_session_detail_endpoint(client):
    sessions = client.get("/api/sessions").json()["sessions"]
    target = sessions[0]

    response = client.get(f"/api/sessions/{target['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == target["id"]


def test_session_detail_returns_404_for_unknown_id(client):
    response = client.get("/api/sessions/does-not-exist")
    assert response.status_code == 404


# ── Projects ────────────────────────────────────────────────────────────────

def test_mock_repositories_carry_git_metadata():
    for repo in get_mock_repositories():
        assert repo["path"].startswith("/")
        assert repo["branch"]
        assert "dirty" in repo


def test_every_session_path_maps_to_a_repository():
    """The projects view joins sessions to repos on ProjectPath."""
    sessions, _ = get_mock_sessions()
    known = {r["path"] for r in get_mock_repositories()}
    assert {s["ProjectPath"] for s in sessions} <= known


def test_serialize_project_combines_repo_and_sessions():
    repo = {
        "path": "/tmp/demo", "name": "demo", "branch": "develop",
        "defaultBranch": "main", "remote": None, "dirty": True,
        "changedFiles": 3, "ahead": 1, "behind": 0,
        "lastCommit": {"hash": "abc1234", "message": "wip", "author": "me", "at": 1_700_000_000},
    }
    sessions = [
        {"Status": "Work", "Project": "demo", "AI": "CL", "mtime": 200, "InputTokens": 10},
        {"Status": "Wait", "Project": "demo", "AI": "CL", "mtime": 100, "InputTokens": 5},
    ]
    result = serialize_project(repo, sessions)

    assert result["id"] == "demo"
    assert result["git"]["branch"] == "develop"
    assert result["git"]["lastCommit"]["hash"] == "abc1234"
    assert result["stats"]["sessions"] == {"total": 2, "active": 1, "idle": 1}
    assert result["agents"] == ["CL"]
    # The project's recency is that of its most recent session.
    assert result["updatedAt"] == 200


def test_serialize_project_without_sessions():
    repo = {"path": "/tmp/x", "name": "x", "branch": "main", "lastCommit": {}}
    result = serialize_project(repo, [])

    assert result["stats"]["sessions"]["total"] == 0
    assert result["updatedAt"] == 0
    assert result["agents"] == []


def test_summarize_sessions_derives_totals_when_not_given():
    sessions = [
        {"Status": "Work", "Project": "a", "InputTokens": 10, "OutputTokens": 2,
         "CacheR": 5, "CacheW": 1},
    ]
    result = summarize_sessions(sessions)
    assert result["tokens"]["total"] == 18
    assert result["tokens"]["input"] == 10


def test_projects_endpoint_groups_sessions(client):
    projects = client.get("/api/projects").json()["projects"]
    assert projects

    by_id = {p["id"]: p for p in projects}
    # mathtools has sessions from Claude, Opencode and Codex.
    assert by_id["mathtools"]["stats"]["sessions"]["total"] == 4
    assert by_id["mathtools"]["agents"] == ["CL", "CX", "OC"]
    assert by_id["mathtools"]["git"]["branch"] == "develop"

    # Ordered by most recent activity.
    updated = [p["updatedAt"] for p in projects]
    assert updated == sorted(updated, reverse=True)


def test_project_detail_includes_only_its_own_sessions(client):
    detail = client.get("/api/projects/mathtools").json()

    assert detail["id"] == "mathtools"
    assert len(detail["sessions"]) == 4
    assert all(s["project"] == "mathtools" for s in detail["sessions"])

    timestamps = [s["updatedAt"] for s in detail["sessions"]]
    assert timestamps == sorted(timestamps, reverse=True)


def test_project_detail_returns_404_for_unknown_project(client):
    assert client.get("/api/projects/nope").status_code == 404


def test_project_session_counts_add_up_to_the_global_total(client):
    projects = client.get("/api/projects").json()["projects"]
    sessions = client.get("/api/sessions").json()["sessions"]

    assert sum(p["stats"]["sessions"]["total"] for p in projects) == len(sessions)


# ── Sessions grouped by provider ────────────────────────────────────────────

def test_project_detail_groups_sessions_by_provider(client):
    detail = client.get("/api/projects/mathtools").json()
    groups = detail["providers"]

    # mathtools has Claude, Opencode and Codex sessions in the mock.
    assert [g["tag"] for g in groups] == ["CL", "OC", "CX"]
    assert sum(len(g["sessions"]) for g in groups) == len(detail["sessions"])

    for group in groups:
        assert group["stats"]["sessions"]["total"] == len(group["sessions"])
        assert all(s["agent"] == group["tag"] for s in group["sessions"])


def test_provider_groups_omit_providers_without_sessions(client):
    """dotfiles only has a Claude session, so no empty groups appear."""
    groups = client.get("/api/projects/dotfiles").json()["providers"]
    assert [g["tag"] for g in groups] == ["CL"]


def test_unreported_metrics_stay_none_rather_than_zero(client):
    """
    Codex reports no cache usage and no turn count. Those must serialize as
    null so the UI shows "—" instead of a zero it would read as a real value.
    """
    groups = client.get("/api/projects/mathtools").json()["providers"]
    codex = next(g for g in groups if g["tag"] == "CX")
    session = codex["sessions"][0]

    assert session["tokens"]["cacheRead"] is None
    assert session["tokens"]["cacheWrite"] is None
    assert session["turnCount"] is None
    # ...but the aggregate still counts them as zero.
    assert codex["stats"]["tokens"]["cacheRead"] == 0
    assert codex["stats"]["tokens"]["total"] > 0


# ── Chat transcripts ────────────────────────────────────────────────────────

def test_mock_chat_falls_back_for_unknown_sessions():
    assert get_mock_chat("does-not-exist")


def test_serialize_message_keeps_optional_fields():
    result = serialize_message({"role": "tool", "text": "Read(x)", "at": 1, "tool": {"name": "Read"}})
    assert result["role"] == "tool"
    assert result["tool"]["name"] == "Read"
    assert result["tokens"] is None


def test_session_messages_endpoint(client):
    sessions = client.get("/api/sessions").json()["sessions"]
    target = next(s for s in sessions if s["agent"] == "CL")

    body = client.get(f"/api/sessions/{target['id']}/messages").json()
    assert body["sessionId"] == target["id"]
    assert body["messages"]
    assert all(m["role"] in {"user", "assistant", "tool"} for m in body["messages"])


def test_session_messages_404_for_unknown_session(client):
    assert client.get("/api/sessions/nope/messages").status_code == 404


# ── Harness ─────────────────────────────────────────────────────────────────

def test_mock_harness_is_empty_for_untracked_paths():
    assert get_mock_harness("/nowhere") == {}


def test_serialize_harness_takes_component_types_from_the_installer():
    """supportedComponents must come from ENVIRONMENTS, not a second list."""
    provider = {"id": "claude", "label": "Claude Code", "tag": "CL", "accent": "#000"}
    env = {
        "target_dir": ".claude",
        "global_dir": "~/.claude",
        "sources": [
            ("framework", "src/agents", "agents", "~/.claude/agents"),
            ("skills", "skills", "skills", "~/.claude/skills"),
        ],
    }
    result = serialize_harness(provider, None, env)

    assert result["supportedComponents"] == ["agents", "skills"]
    assert result["installable"] is True
    assert result["installed"] is False
    assert result["componentCount"] == 0


def test_serialize_harness_without_installer_support():
    provider = {"id": "codex", "label": "Codex", "tag": "CX", "accent": "#000"}
    result = serialize_harness(provider, None, None)

    assert result["installable"] is False
    assert result["supportedComponents"] == []
    assert result["targetDir"] is None


def test_harness_endpoint_lists_all_providers(client):
    body = client.get("/api/projects/mathtools/harness").json()
    providers = {p["id"]: p for p in body["providers"]}

    assert len(providers) == len(AGENT_PROVIDERS)
    assert providers["claude"]["installed"] is True
    assert providers["claude"]["componentCount"] == 7
    assert providers["claude"]["updateAvailable"] is True
    # Declared but not installed in this project.
    assert providers["gemini"]["installed"] is False
    assert providers["gemini"]["installable"] is True
    # Codex has sessions but no environment the installer can deploy.
    assert providers["codex"]["installable"] is False


def test_harness_404_for_unknown_project(client):
    assert client.get("/api/projects/nope/harness").status_code == 404


def test_install_harness_is_simulated_only(client):
    response = client.post(
        "/api/projects/mathtools/harness/claude",
        json={"scope": "local", "components": ["skills"]},
    )
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "simulated"
    assert body["applied"] is False
    assert body["components"] == ["skills"]
    assert body["target"] == "/root/mathtools/.claude"


def test_install_harness_global_scope_targets_the_home_dir(client):
    body = client.post(
        "/api/projects/mathtools/harness/claude", json={"scope": "global"}
    ).json()
    assert body["target"] == "~/.claude"


def test_install_harness_defaults_to_every_component(client):
    body = client.post("/api/projects/mathtools/harness/claude", json={}).json()
    assert body["components"] == ["agents", "commands", "skills"]


def test_install_harness_rejects_a_provider_without_an_environment(client):
    response = client.post("/api/projects/mathtools/harness/codex", json={})
    assert response.status_code == 400


def test_install_harness_404s(client):
    assert client.post("/api/projects/nope/harness/claude", json={}).status_code == 404
    assert client.post("/api/projects/mathtools/harness/nope", json={}).status_code == 404


# ── Frontend mount ──────────────────────────────────────────────────────────
# The API keeps working when the repo root is resolved wrongly, so without
# these the frontend can stop being served and every test still passes.

def test_repo_root_is_the_directory_holding_pyproject():
    root = _repo_root()
    assert (root / "pyproject.toml").is_file(), f"{root} is not the repo root"


def test_repo_root_resolves_the_frontend_and_source_tree():
    """Pins the paths the dist mount depends on, across package moves."""
    root = _repo_root()
    assert (root / "src" / "web" / "server.py").is_file()
    assert (root / FRONTEND_DIST_DIR).parent.is_dir(), "src/frontend is missing"


def test_built_frontend_is_mounted_when_present(client):
    """A built dist must be served at / — and deep links must not 404."""
    if not (_repo_root() / FRONTEND_DIST_DIR).is_dir():
        pytest.skip("frontend not built (npm run build)")

    assert client.get("/").status_code == 200
    # BrowserRouter deep link falls back to index.html...
    assert client.get("/projects/mathtools").status_code == 200
    # ...but a missing asset must stay a 404, or the browser gets HTML
    # where it expects a script and the page fails silently.
    assert client.get("/assets/does-not-exist.js").status_code == 404


# ── Dashboard launcher ──────────────────────────────────────────────────────

def test_web_dashboard_defaults():
    dashboard = WebDashboard()
    assert dashboard.port == WEB_PORT


def test_web_dashboard_accepts_overrides():
    dashboard = WebDashboard(host="0.0.0.0", port=9000)
    assert (dashboard.host, dashboard.port) == ("0.0.0.0", 9000)
