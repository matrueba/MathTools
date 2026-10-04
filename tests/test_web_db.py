import sqlite3

import pytest
from fastapi.testclient import TestClient

from web.db import Database, DuplicateProjectError, ProjectStore
from web.server import create_app


@pytest.fixture
def database(tmp_path):
    db = Database(tmp_path / "nested" / "mathtools.db")
    db.init_schema()
    return db


@pytest.fixture
def git_repo(tmp_path):
    repo = tmp_path / "My Repo"
    (repo / ".git").mkdir(parents=True)
    return repo


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(db_path=tmp_path / "mathtools.db"))


# ── Database ────────────────────────────────────────────────────────────────

def test_init_schema_creates_parent_dir_and_is_idempotent(database):
    assert database.path.is_file()
    database.init_schema()

    with database.connect() as conn:
        tables = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master")}
    assert "projects" in tables


def test_connect_rolls_back_on_error(database):
    with pytest.raises(RuntimeError):
        with database.connect() as conn:
            conn.execute(
                "INSERT INTO projects VALUES ('a', 'a', '/a', 0)"
            )
            raise RuntimeError

    assert ProjectStore(database).list() == []


# ── ProjectStore ────────────────────────────────────────────────────────────

def test_project_store_round_trip(database):
    store = ProjectStore(database)
    created = store.create("repo", "Repo", "/tmp/repo")

    assert store.get("repo") == created
    assert store.list() == [created]
    assert store.get("missing") is None


@pytest.mark.parametrize("project_id, path", [("repo", "/other"), ("other", "/tmp/repo")])
def test_project_store_rejects_duplicate_id_or_path(database, project_id, path):
    store = ProjectStore(database)
    store.create("repo", "Repo", "/tmp/repo")

    with pytest.raises(DuplicateProjectError):
        store.create(project_id, "Other", path)


# ── POST /api/projects ──────────────────────────────────────────────────────

def test_create_project_persists_and_defaults_name_to_folder(client, git_repo):
    res = client.post("/api/projects", json={"path": str(git_repo)})

    assert res.status_code == 201
    body = res.json()
    assert body["id"] == "my-repo"
    assert body["name"] == "My Repo"
    assert body["path"] == str(git_repo.resolve())


def test_create_project_uses_explicit_name(client, git_repo):
    res = client.post("/api/projects", json={"path": str(git_repo), "name": "Custom"})
    assert res.status_code == 201
    assert res.json()["id"] == "custom"


def test_create_project_rejects_missing_dir(client, tmp_path):
    res = client.post("/api/projects", json={"path": str(tmp_path / "nope")})
    assert res.status_code == 400


def test_create_project_rejects_non_git_dir(client, tmp_path):
    res = client.post("/api/projects", json={"path": str(tmp_path)})
    assert res.status_code == 400
    assert "git" in res.json()["detail"]


def test_create_project_conflicts_on_same_path(client, git_repo):
    assert client.post("/api/projects", json={"path": str(git_repo)}).status_code == 201

    # Same repo, different spelling of the path, different name.
    res = client.post(
        "/api/projects", json={"path": f"{git_repo}/.", "name": "Another"}
    )
    assert res.status_code == 409


def test_create_project_requires_path(client):
    assert client.post("/api/projects", json={}).status_code == 422


def test_registered_project_is_listed_and_reachable(client, git_repo):
    client.post("/api/projects", json={"path": str(git_repo)})

    projects = client.get("/api/projects").json()["projects"]
    added = next(p for p in projects if p["id"] == "my-repo")
    assert added["path"] == str(git_repo.resolve())
    assert added["git"]["lastCommit"] is None

    assert client.get("/api/projects/my-repo").status_code == 200


# ── GET /api/fs/browse ──────────────────────────────────────────────────────

def test_browse_lists_subfolders_and_flags_git_repos(client, tmp_path, git_repo):
    (tmp_path / "plain").mkdir()
    (tmp_path / ".hidden").mkdir()
    (tmp_path / "file.txt").write_text("x")

    body = client.get("/api/fs/browse", params={"path": str(tmp_path)}).json()

    assert body["path"] == str(tmp_path.resolve())
    assert body["parent"] == str(tmp_path.resolve().parent)
    assert body["isGitRepo"] is False
    entries = {e["name"]: e["isGitRepo"] for e in body["entries"]}
    assert entries == {"My Repo": True, "plain": False}


def test_browse_reports_the_current_folder_as_repo(client, git_repo):
    body = client.get("/api/fs/browse", params={"path": str(git_repo)}).json()
    assert body["isGitRepo"] is True


def test_browse_accepts_git_file_from_worktrees(client, tmp_path):
    worktree = tmp_path / "wt"
    worktree.mkdir()
    (worktree / ".git").write_text("gitdir: /elsewhere")

    body = client.get("/api/fs/browse", params={"path": str(tmp_path)}).json()
    assert body["entries"] == [{"name": "wt", "path": str(worktree), "isGitRepo": True}]


def test_browse_missing_path_is_404(client, tmp_path):
    res = client.get("/api/fs/browse", params={"path": str(tmp_path / "nope")})
    assert res.status_code == 404


# ── DataStore.get_repo_info ─────────────────────────────────────────────────

import subprocess

from web.data import DataStore


def _git(cwd, *args):
    subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.name=tester", "-c", "user.email=t@t", *args],
        check=True,
        capture_output=True,
    )


@pytest.fixture
def real_repo(tmp_path):
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "--bare", "-b", "main", str(origin))

    seed = tmp_path / "seed"
    _git(tmp_path, "init", "-b", "main", str(seed))
    (seed / "a.txt").write_text("a")
    _git(seed, "add", ".")
    _git(seed, "commit", "-m", "first commit")
    _git(seed, "push", str(origin), "main")

    repo = tmp_path / "clone"
    _git(tmp_path, "clone", str(origin), str(repo))
    return repo, origin


def _row(path, project_id="clone"):
    return {"id": project_id, "name": project_id, "path": str(path), "createdAt": 1.0}


def test_repo_info_matches_the_mock_repository_shape(database, real_repo):
    from web.mock_data import get_mock_repositories

    repo, _ = real_repo
    info = DataStore(ProjectStore(database)).get_repo_info(_row(repo))

    assert set(get_mock_repositories()[0]) <= set(info)
    assert info["branch"] == "main"
    assert info["defaultBranch"] == "main"
    assert info["remote"] == str(repo.parent / "origin.git")
    assert info["dirty"] is False and info["changedFiles"] == 0
    assert (info["ahead"], info["behind"]) == (0, 0)
    assert info["lastCommit"]["message"] == "first commit"
    assert info["lastCommit"]["author"] == "tester"
    assert isinstance(info["lastCommit"]["at"], float)


def test_repo_info_reports_changes_and_divergence(database, real_repo):
    repo, _ = real_repo
    (repo / "a.txt").write_text("changed")
    (repo / "new.txt").write_text("new")
    _git(repo, "commit", "--allow-empty", "-m", "local only")

    info = DataStore(ProjectStore(database)).get_repo_info(_row(repo))

    assert info["dirty"] is True
    assert info["changedFiles"] == 2
    assert (info["ahead"], info["behind"]) == (1, 0)
    assert info["lastCommit"]["message"] == "local only"


def test_repo_info_degrades_when_git_cannot_answer(database, tmp_path):
    info = DataStore(ProjectStore(database)).get_repo_info(_row(tmp_path / "gone"))

    assert info["branch"] is None
    assert info["remote"] is None
    assert info["lastCommit"] is None
    assert info["dirty"] is False
