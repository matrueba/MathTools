"""Sessions are nested under project → agent; there is no flat session API."""

import pytest


@pytest.fixture
def client(web_client):
    return web_client


def _first(client, agent="claude"):
    sessions = client.get(f"/api/projects/mathtools/agents/{agent}/sessions").json()
    return sessions["sessions"][0]


def test_flat_session_routes_are_gone(client):
    assert client.get("/api/sessions").status_code == 404
    assert client.get("/api/stats").status_code == 404


def test_project_detail_nests_sessions_under_agents(client):
    detail = client.get("/api/projects/mathtools").json()

    assert "sessions" not in detail and "providers" not in detail
    agents = {a["id"]: a for a in detail["agents"]}
    # mathtools has Claude, Opencode and Codex sessions in the mock.
    assert set(agents) == {"claude", "opencode", "codex"}
    assert sum(len(a["sessions"]) for a in agents.values()) == detail["stats"]["sessions"]["total"]
    for agent in agents.values():
        assert {s["agent"] for s in agent["sessions"]} == {agent["tag"]}


def test_project_agents_endpoint_matches_project_detail(client):
    body = client.get("/api/projects/mathtools/agents").json()
    assert body["projectId"] == "mathtools"
    assert body["agents"] == client.get("/api/projects/mathtools").json()["agents"]


def test_agent_sessions_are_scoped_and_sorted(client):
    body = client.get("/api/projects/mathtools/agents/claude/sessions").json()

    assert body["sessions"]
    assert {s["agent"] for s in body["sessions"]} == {"CL"}
    assert body["stats"]["sessions"]["total"] == len(body["sessions"])
    timestamps = [s["updatedAt"] for s in body["sessions"]]
    assert timestamps == sorted(timestamps, reverse=True)


def test_agent_without_sessions_returns_empty_list(client):
    # dotfiles only has a Claude session in the mock.
    body = client.get("/api/projects/dotfiles/agents/codex/sessions").json()
    assert body["sessions"] == []
    assert body["stats"]["sessions"]["total"] == 0


def test_session_detail_and_messages(client):
    target = _first(client)
    base = f"/api/projects/mathtools/agents/claude/sessions/{target['id']}"

    assert client.get(base).json()["id"] == target["id"]
    messages = client.get(f"{base}/messages").json()
    assert messages["sessionId"] == target["id"]
    assert isinstance(messages["messages"], list)


def test_session_under_the_wrong_agent_is_404(client):
    target = _first(client, "claude")
    res = client.get(f"/api/projects/mathtools/agents/opencode/sessions/{target['id']}")
    assert res.status_code == 404


@pytest.mark.parametrize("path", [
    "/api/projects/nope/agents",
    "/api/projects/nope/agents/claude/sessions",
    "/api/projects/mathtools/agents/nope/sessions",
    "/api/projects/mathtools/agents/claude/sessions/nope",
    "/api/projects/mathtools/agents/claude/sessions/nope/messages",
])
def test_unknown_project_agent_or_session_is_404(client, path):
    assert client.get(path).status_code == 404


def test_unreported_metrics_stay_none_rather_than_zero(client):
    """
    Codex reports no cache usage and no turn count. Those must serialize as
    null so the UI shows "—" instead of a zero it would read as a real value.
    """
    body = client.get("/api/projects/mathtools/agents/codex/sessions").json()
    session = body["sessions"][0]

    assert session["tokens"]["cacheRead"] is None
    assert session["tokens"]["cacheWrite"] is None
    assert session["turnCount"] is None
    # ...but the aggregate still counts them as zero.
    assert body["stats"]["tokens"]["cacheRead"] == 0
    assert body["stats"]["tokens"]["total"] > 0


# ── Interactions (agent → subagent graph; mock-backed for now) ──────────────

def test_interactions_return_a_graph_flagged_as_mock(client):
    target = _first(client)
    url = f"/api/projects/mathtools/agents/claude/sessions/{target['id']}/interactions"
    body = client.get(url).json()

    assert body["sessionId"] == target["id"]
    assert body["mock"] is True
    assert body["nodes"] and body["edges"]


def test_interaction_graph_is_a_tree_rooted_at_the_main_agent(client):
    target = _first(client)
    url = f"/api/projects/mathtools/agents/claude/sessions/{target['id']}/interactions"
    body = client.get(url).json()

    ids = {n["id"] for n in body["nodes"]}
    assert len(ids) == len(body["nodes"])
    for edge in body["edges"]:
        assert edge["from"] in ids and edge["to"] in ids
    # Every node but one has exactly one parent: a tree, rooted at the agent.
    targets = [e["to"] for e in body["edges"]]
    assert len(targets) == len(set(targets))
    (root,) = ids - set(targets)
    assert next(n for n in body["nodes"] if n["id"] == root)["kind"] == "agent"
    # Launch order is 1..n among each parent's children.
    by_parent = {}
    for edge in body["edges"]:
        by_parent.setdefault(edge["from"], []).append(edge["order"])
    for orders in by_parent.values():
        assert sorted(orders) == list(range(1, len(orders) + 1))


def test_interactions_of_an_unknown_session_are_404(client):
    url = "/api/projects/mathtools/agents/claude/sessions/nope/interactions"
    assert client.get(url).status_code == 404
