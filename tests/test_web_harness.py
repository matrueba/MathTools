"""
The real harness: detection on disk, install, update and cleanup.

GitHub is replaced by the in-memory zips from conftest (download) and a
dict of revisions (ls-remote); everything else runs for real against git
repositories and a HOME under tmp_path.
"""

import json
import os

import pytest

from web import harness, installer

URL = "/api/projects/mathtools/harness"


@pytest.fixture
def github(monkeypatch, framework_zip, skills_zip):
    """Offline GitHub: archives from conftest, revisions you can move."""
    state = {
        "zips": {"framework": framework_zip, "skills": skills_zip},
        "revisions": {"framework": "f1", "skills": "s1"},
        "downloads": [],
    }

    def download(names=None):
        state["downloads"].append(sorted(names or state["zips"]))
        return {n: z for n, z in state["zips"].items() if names is None or n in names}

    monkeypatch.setattr(installer, "download_repo_zips", download)
    monkeypatch.setattr(installer, "remote_revision", lambda repo: state["revisions"].get(repo))
    return state


def _providers(client, project="mathtools"):
    body = client.get(f"/api/projects/{project}/harness").json()
    return {p["id"]: p for p in body["providers"]}


def _install(client, provider="claude", **body):
    return client.post(f"{URL}/{provider}", json=body)


# ── Detection ───────────────────────────────────────────────────────────────

def test_nothing_on_disk_means_not_installed(web_client, github):
    providers = _providers(web_client)

    assert set(providers) == {"claude", "opencode", "codex"}
    assert providers["claude"]["installed"] is False
    assert providers["claude"]["installable"] is True
    assert providers["claude"]["existing"] == {"local": [], "global": []}
    # Codex has sessions but no environment the installer can deploy.
    assert providers["codex"]["installable"] is False


def test_items_put_there_by_hand_are_detected_with_their_description(web_client, github):
    repo = web_client.repo_paths["mathtools"]
    agents = os.path.join(repo, ".claude", "agents")
    os.makedirs(os.path.join(repo, ".claude", "skills", "tidy"))
    os.makedirs(agents)
    with open(os.path.join(agents, "reviewer.md"), "w") as f:
        f.write("---\nname: reviewer\ndescription: 'Reviews diffs'\n---\nbody")
    with open(os.path.join(repo, ".claude", "skills", "tidy", "SKILL.md"), "w") as f:
        f.write("---\ndescription: Tidies code\n---\n")
    with open(os.path.join(agents, ".hidden"), "w") as f:
        f.write("ignored")

    claude = _providers(web_client)["claude"]
    assert claude["installed"] is True
    assert claude["scope"] == "local"
    assert claude["components"]["agents"] == [{"name": "reviewer", "description": "Reviews diffs"}]
    assert claude["components"]["skills"] == [{"name": "tidy", "description": "Tidies code"}]
    assert claude["componentCount"] == 2
    # Not installed by mathtools: no install date, update state unknown.
    assert claude["installedAt"] is None
    assert claude["updateAvailable"] is None
    assert claude["existing"]["local"] == [".claude"]


def test_a_global_harness_is_found_under_home(web_client, github):
    home = os.environ["HOME"]
    os.makedirs(os.path.join(home, ".claude", "commands"))
    open(os.path.join(home, ".claude", "commands", "commit.md"), "w").close()

    claude = _providers(web_client)["claude"]
    assert claude["scope"] == "global"
    assert claude["components"]["commands"] == [{"name": "commit", "description": ""}]


# ── Install ─────────────────────────────────────────────────────────────────

def test_install_writes_the_selected_components_and_a_manifest(web_client, github):
    res = _install(web_client, scope="local", components=["agents", "skills"])
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "installed"
    assert body["components"] == ["agents", "skills"]
    assert body["written"] > 0
    assert body["removed"] == []

    repo = web_client.repo_paths["mathtools"]
    assert os.path.isfile(os.path.join(repo, ".claude", "agents", "agent1", "config.yaml"))
    assert os.path.isfile(os.path.join(repo, ".claude", "skills", "skill2", "SKILL.md"))
    assert not os.path.exists(os.path.join(repo, ".claude", "commands"))

    manifest = json.loads(open(os.path.join(repo, ".claude", harness.MANIFEST_NAME)).read())
    assert manifest["components"] == ["agents", "skills"]
    assert manifest["revisions"] == {"agents": "f1", "skills": "s1"}
    assert ".claude/agents/agent1/config.yaml" in manifest["files"]

    claude = _providers(web_client)["claude"]
    assert claude["installed"] and claude["scope"] == "local"
    assert sorted(i["name"] for i in claude["components"]["agents"]) == ["agent1", "agent2"]
    assert claude["installedAt"] > 0
    assert claude["updateAvailable"] is False


def test_install_downloads_only_the_repositories_it_needs(web_client, github):
    _install(web_client, components=["skills"])
    assert github["downloads"] == [["skills"]]


def test_install_defaults_to_local_and_every_component(web_client, github):
    body = _install(web_client).json()
    assert body["scope"] == "local"
    assert body["components"] == ["agents", "commands", "skills"]
    assert body["target"] == f"{web_client.repo_paths['mathtools']}/.claude"


def test_global_install_lands_in_home_claude_with_its_manifest(web_client, github):
    body = _install(web_client, scope="global", components=["commands"]).json()
    home = os.environ["HOME"]

    assert body["target"] == os.path.join(home, ".claude")
    assert os.path.isfile(os.path.join(home, ".claude", "commands", "cmd1", "run.sh"))
    assert os.path.isfile(os.path.join(home, ".claude", harness.MANIFEST_NAME))
    assert not os.path.exists(os.path.join(web_client.repo_paths["mathtools"], ".claude"))

    claude = _providers(web_client)["claude"]
    assert claude["scope"] == "global"
    assert claude["root"] == os.path.join(home, ".claude")
    assert claude["installedAt"] > 0


def test_install_roots_are_the_repo_and_home_claude_folders(web_client, github):
    claude = _providers(web_client)["claude"]
    assert claude["roots"] == {
        "local": os.path.join(web_client.repo_paths["mathtools"], ".claude"),
        "global": os.path.join(os.environ["HOME"], ".claude"),
    }
    assert claude["root"] is None  # nothing installed yet


def test_a_global_manifest_in_the_old_location_is_read_then_moved(web_client, github):
    home = os.environ["HOME"]
    os.makedirs(os.path.join(home, ".claude", "agents", "old"))
    legacy = os.path.join(home, ".mathtools", "harness", "claude.json")
    os.makedirs(os.path.dirname(legacy))
    with open(legacy, "w") as f:
        json.dump({"scope": "global", "installedAt": 123, "revisions": {"agents": "f1"},
                   "components": ["agents"], "files": []}, f)

    claude = _providers(web_client)["claude"]
    assert claude["installedAt"] == 123 and claude["updateAvailable"] is False

    _install(web_client, scope="global", components=["agents"])
    assert not os.path.exists(legacy)
    assert os.path.isfile(os.path.join(home, ".claude", harness.MANIFEST_NAME))


def test_a_new_upstream_revision_shows_as_an_update(web_client, github):
    _install(web_client, components=["agents", "commands"])
    github["revisions"]["framework"] = "f2"
    assert _providers(web_client)["claude"]["updateAvailable"] is True

    github["revisions"]["framework"] = None  # offline
    assert _providers(web_client)["claude"]["updateAvailable"] is None


def test_update_removes_only_files_it_installed_that_upstream_dropped(
    web_client, github, sample_zip_bytes
):
    repo = web_client.repo_paths["mathtools"]
    _install(web_client, components=["agents", "commands"])
    own = os.path.join(repo, ".claude", "agents", "mine.md")
    open(own, "w").close()

    # Upstream drops agent2 and moves on.
    github["zips"]["framework"] = sample_zip_bytes(
        "matrueba-AI-development-framework-main/",
        {"src/agents/agent1/config.yaml": "v2", "src/commands/cmd1/run.sh": "#!/bin/sh"},
    )
    github["revisions"]["framework"] = "f2"
    body = _install(web_client, components=["agents"]).json()

    assert body["removed"] == [
        ".claude/agents/agent1/prompt.md",
        ".claude/agents/agent2/config.yaml",
    ]
    assert not os.path.exists(os.path.join(repo, ".claude", "agents", "agent2"))
    assert open(os.path.join(repo, ".claude", "agents", "agent1", "config.yaml")).read() == "v2"
    assert os.path.exists(own)  # the user's own file is never touched
    # Commands were not reinstalled, so cmd2 stays even though upstream dropped it.
    assert os.path.exists(os.path.join(repo, ".claude", "commands", "cmd2", "run.sh"))

    manifest = json.loads(open(os.path.join(repo, ".claude", harness.MANIFEST_NAME)).read())
    assert manifest["components"] == ["agents", "commands"]
    assert manifest["revisions"] == {"agents": "f2", "commands": "f1"}
    assert ".claude/commands/cmd2/run.sh" in manifest["files"]
    assert ".claude/agents/agent2/config.yaml" not in manifest["files"]
    # Commands are still at f1 while upstream is at f2.
    assert _providers(web_client)["claude"]["updateAvailable"] is True


def test_a_tampered_manifest_cannot_delete_outside_the_harness(web_client, github):
    repo = web_client.repo_paths["mathtools"]
    _install(web_client, components=["agents"])
    victim = os.path.join(repo, "README.md")
    open(victim, "w").close()

    path = os.path.join(repo, ".claude", harness.MANIFEST_NAME)
    manifest = json.loads(open(path).read())
    manifest["files"] += ["README.md", ".claude/agents/../../README.md"]
    open(path, "w").write(json.dumps(manifest))

    _install(web_client, components=["agents"])
    assert os.path.exists(victim)


def test_github_unreachable_is_a_502_and_writes_nothing(web_client, github, monkeypatch):
    def offline(names=None):
        raise installer.requests.ConnectionError("no route to host")

    monkeypatch.setattr(installer, "download_repo_zips", offline)
    res = _install(web_client)
    assert res.status_code == 502
    assert "no route to host" in res.json()["detail"]
    assert not os.path.exists(os.path.join(web_client.repo_paths["mathtools"], ".claude"))


@pytest.mark.parametrize("body", [{"scope": "everywhere"}, {"components": ["rules"]}])
def test_install_rejects_bad_input(web_client, github, body):
    assert _install(web_client, **body).status_code == 400
    assert github["downloads"] == []


def test_install_rejects_a_provider_without_an_environment(web_client, github):
    assert _install(web_client, provider="codex").status_code == 400


def test_install_and_harness_404s(web_client, github):
    assert web_client.post("/api/projects/nope/harness/claude", json={}).status_code == 404
    assert _install(web_client, provider="nope").status_code == 404
    assert web_client.get("/api/projects/nope/harness").status_code == 404


# ── Descriptions ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("content, expected", [
    ("---\ndescription: Inline one\n---\nbody", "Inline one"),
    ('---\ndescription: "Quoted"\n---\n', "Quoted"),
    ("---\nname: x\ndescription: >\n  Folded over\n  two lines.\nother: y\n---\n", "Folded over two lines."),
    ("---\ndescription: |-\n  Literal\n---\n", "Literal"),
    ("Review the file $ARGUMENTS\nand more", "Review the file $ARGUMENTS"),
    ("---\nname: x\n---\n\n# Heading as summary\n", "Heading as summary"),
    ("", ""),
])
def test_item_descriptions(tmp_path, content, expected):
    path = tmp_path / "item.md"
    path.write_text(content)
    assert harness._description(path) == expected


def test_non_text_items_have_no_description(tmp_path):
    path = tmp_path / "run.sh"
    path.write_text("#!/bin/sh\necho hi")
    assert harness._description(path) == ""
