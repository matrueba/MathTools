"""
The harness of a project: what is deployed on disk, and deploying it.

Each scope has one install root, derived from the ENVIRONMENTS entry:

    local   <project>/<target_dir>       e.g. <repo>/.claude
    global  <global_dir>, expanded       e.g. $HOME/.claude

Detection reads the same destinations the installer writes to, never a
second list:

    local   <project>/<target_dir>/<dest_subpath>/<item>
    global  <global_path>/<item>                    (one path per source)

(for Claude Code every global_path sits inside $HOME/.claude)

and lists every item found there, whoever put it, with the `description` from
its frontmatter. Local wins over global when a project has both, because that
is what the agent itself loads first.

An install writes a manifest at the root of the scope it deployed to:

    local   <repo>/.claude/.mathtools-harness.json
    global  $HOME/.claude/.mathtools-harness.json

recording when, which components, the upstream revision each component was
taken from and every file written. That is where `installedAt` and `updateAvailable` come
from (a harness found on disk without a manifest was not installed by us and
reports neither), and what lets an update delete the files it installed last
time that upstream has since removed — only those: files the user added
themselves are never touched.
"""

import json
import os
import re
import threading
import time
from pathlib import Path

from constants.environments import ENVIRONMENTS

from . import installer

MANIFEST_NAME = ".mathtools-harness.json"
# Where global manifests used to live; still read so an earlier global install
# keeps its date and update state, and removed by the next install.
LEGACY_GLOBAL_MANIFEST_DIR = "~/.mathtools/harness"
SCOPES = ("local", "global")

DESCRIPTION_CHARS = 200

# One install at a time: two concurrent ones on the same destination would
# interleave their writes and their manifests.
_install_lock = threading.Lock()


class HarnessError(RuntimeError):
    """An install could not be completed; the message is meant for the user."""


# ── Reading what is on disk ─────────────────────────────────────────────────

_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---[^\n]*\n?", re.S)
_BLOCK_SCALAR = re.compile(r"^[>|][-+]?$")  # YAML `description: >` and friends


def _frontmatter_description(block: str) -> str:
    """
    `description` from a frontmatter block, inline or as a `>`/`|` block
    scalar whose indented lines follow (folded into one line either way).
    """
    lines = block.splitlines()
    for n, line in enumerate(lines):
        if not line.startswith("description:"):
            continue
        value = line.split(":", 1)[1].strip()
        if not _BLOCK_SCALAR.match(value):
            return value.strip("'\"")
        folded = []
        for follow in lines[n + 1:]:
            if follow.strip() and not follow[:1].isspace():
                break
            folded.append(follow.strip())
        return " ".join(part for part in folded if part)
    return ""


def _description(path: Path) -> str:
    """
    What an item is for: its frontmatter `description`, else the first line
    of its body (commands often have no frontmatter at all), or "".

    A file item is read itself; a folder item (a skill) through its SKILL.md
    or README.md. Anything unreadable just has no description.
    """
    if path.is_dir():
        path = next((path / n for n in ("SKILL.md", "README.md") if (path / n).is_file()), None)
        if path is None:
            return ""
    if path.suffix.lower() not in (".md", ".markdown", ".txt"):
        return ""
    try:
        with open(path, encoding="utf-8") as f:
            head = f.read(8192)
    except (OSError, UnicodeDecodeError):
        return ""

    block = _FRONTMATTER.match(head)
    text = _frontmatter_description(block.group(1)) if block else ""
    if not text:
        body = head[block.end():] if block else head
        text = next((ln.strip().lstrip("#").strip() for ln in body.splitlines() if ln.strip()), "")
    return text if len(text) <= DESCRIPTION_CHARS else text[: DESCRIPTION_CHARS - 1] + "…"


def _items(folder: Path) -> list[dict]:
    """Top-level items of one component folder: files by stem, folders by name."""
    try:
        entries = sorted(folder.iterdir())
    except OSError:
        return []
    return [
        {
            "name": entry.name if entry.is_dir() else entry.stem,
            "description": _description(entry),
        }
        for entry in entries
        if not entry.name.startswith(".")
    ]


def _component_dirs(env: dict, scope: str, project_path: str) -> dict[str, Path]:
    """dest_subpath -> where that component lives in `scope`."""
    if scope == "local":
        base = Path(project_path) / env["target_dir"]
        return {dest: base / dest for _, _, dest, _ in env["sources"]}
    return {dest: Path(os.path.expanduser(glob)) for _, _, dest, glob in env["sources"]}


def install_root(env_key: str, scope: str, project_path: str) -> Path:
    """
    The folder a scope installs into: the repository's `<target_dir>` for
    local, the environment's `global_dir` under $HOME for global.
    """
    env = ENVIRONMENTS[env_key]
    if scope == "local":
        return Path(project_path) / env["target_dir"]
    return Path(os.path.expanduser(env["global_dir"]))


def install_roots(env_key: str, project_path: str) -> dict[str, str]:
    """Both install roots as absolute paths, for the UI to show."""
    return {scope: str(install_root(env_key, scope, project_path)) for scope in SCOPES}


def _manifest_path(env_key: str, scope: str, project_path: str) -> Path:
    return install_root(env_key, scope, project_path) / MANIFEST_NAME


def _legacy_manifest_path(env_key: str, scope: str) -> Path | None:
    if scope != "global":
        return None
    return Path(os.path.expanduser(LEGACY_GLOBAL_MANIFEST_DIR)) / f"{env_key}.json"


def _load_manifest(env_key: str, scope: str, project_path: str) -> dict | None:
    """The scope's manifest, falling back to where global ones used to be."""
    manifest = _read_manifest(_manifest_path(env_key, scope, project_path))
    legacy = _legacy_manifest_path(env_key, scope)
    if manifest is None and legacy is not None:
        manifest = _read_manifest(legacy)
    return manifest


def _read_manifest(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _component_repos(env: dict) -> dict[str, str]:
    """dest_subpath -> the repository its files come from."""
    return {dest: repo for repo, _, dest, _ in env["sources"]}


def _update_available(manifest: dict | None, env: dict) -> bool | None:
    """
    True when upstream moved past the revision any installed component was
    taken from. Tracked per component, not per repository: two components
    can share a repository and still have been installed at different times.

    None when that cannot be told: no manifest (not installed by us), no
    recorded revision, or upstream unreachable.
    """
    recorded = (manifest or {}).get("revisions") or {}
    if not isinstance(recorded, dict) or not recorded:
        return None
    repos = _component_repos(env)
    unknown = False
    for component, revision in recorded.items():
        current = installer.remote_revision(repos[component]) if component in repos else None
        if current is None or revision is None:
            unknown = True
        elif current != revision:
            return True
    return None if unknown else False


def detect_harness(env_key: str, project_path: str) -> dict | None:
    """
    The harness of one environment as seen from `project_path`, or None.

    Shape (what `serialize_harness` consumes): scope, installedAt,
    updateAvailable, components {dest_subpath: [{name, description}]}.
    """
    env = ENVIRONMENTS[env_key]
    for scope in SCOPES:
        components = {
            dest: _items(folder)
            for dest, folder in _component_dirs(env, scope, project_path).items()
        }
        if not any(components.values()):
            continue
        manifest = _load_manifest(env_key, scope, project_path)
        return {
            "scope": scope,
            "installedAt": (manifest or {}).get("installedAt"),
            "updateAvailable": _update_available(manifest, env),
            "components": components,
        }
    return None


def existing_targets(env_key: str, project_path: str) -> dict[str, list[str]]:
    """Per scope, the destinations an install would write into that already exist."""
    return {
        scope: installer.get_existing_folders([env_key], {env_key: scope}, project_path)
        for scope in SCOPES
    }


# ── Installing ──────────────────────────────────────────────────────────────

def _resolve(written: str, scope: str, project_path: str) -> Path:
    """A path as recorded in a manifest, back to an absolute path."""
    if scope == "global":
        return Path(os.path.expanduser(written))
    return Path(project_path) / written


def _remove_stale(old: dict | None, written: set[str], components: list[str],
                  env: dict, scope: str, project_path: str) -> list[str]:
    """
    Delete files the previous install wrote, for the components being
    reinstalled, that this install did not write again (removed upstream).

    Every path is checked to lie inside one of the environment's component
    folders before it is deleted, so a hand-edited manifest cannot point the
    cleanup anywhere else.
    """
    if not old or old.get("scope") != scope:
        return []
    roots = {
        dest: folder.resolve()
        for dest, folder in _component_dirs(env, scope, project_path).items()
        if dest in components
    }
    removed = []
    for recorded in old.get("files") or []:
        if not isinstance(recorded, str) or recorded in written:
            continue
        path = _resolve(recorded, scope, project_path).resolve()
        if not any(path.is_relative_to(root) for root in roots.values()):
            continue
        try:
            path.unlink()
        except OSError:
            continue
        removed.append(recorded)
        # Drop folders the removal left empty, up to the component root.
        parent = path.parent
        while parent not in roots.values() and any(parent.is_relative_to(r) for r in roots.values()):
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
    return removed


def install_harness(env_key: str, scope: str, components: list[str], project_path: str) -> dict:
    """
    Download the framework repositories and deploy `components` of one
    environment into `scope`.

    Components not selected are left exactly as they are, and stay in the
    manifest from the previous install. Raises HarnessError with a
    user-facing message when GitHub cannot be reached or the disk refuses.
    """
    env = ENVIRONMENTS[env_key]
    sources = [s for s in env["sources"] if s[2] in components]
    repos = sorted({repo for repo, _, _, _ in sources})

    with _install_lock:
        by_repo = {repo: installer.remote_revision(repo) for repo in repos}
        revisions = {dest: by_repo[repo] for repo, _, dest, _ in sources}
        try:
            zips = installer.download_repo_zips(repos)
        except installer.requests.RequestException as exc:
            raise HarnessError(f"Could not download the framework from GitHub: {exc}") from exc

        # An empty list selects nothing, so unselected sources are skipped.
        selections = {
            src: ("all" if dest in components else [])
            for _, src, dest, _ in env["sources"]
        }
        try:
            written, location = installer.extract_environment(
                zips, env_key, scope, selections, project_path
            )
        except OSError as exc:
            raise HarnessError(f"Could not write the harness: {exc}") from exc

        manifest_path = _manifest_path(env_key, scope, project_path)
        old = _load_manifest(env_key, scope, project_path)
        removed = _remove_stale(old, set(written), components, env, scope, project_path)

        # Keep what earlier installs recorded for the components left alone.
        kept_files, kept_components, kept_revisions = [], [], {}
        if old and old.get("scope") == scope:
            dirs = _component_dirs(env, scope, project_path)
            for recorded in old.get("files") or []:
                if not isinstance(recorded, str):
                    continue
                path = _resolve(recorded, scope, project_path)
                if any(
                    path.is_relative_to(folder)
                    for dest, folder in dirs.items()
                    if dest not in components
                ):
                    kept_files.append(recorded)
            kept_components = [c for c in old.get("components") or [] if c not in components]
            kept_revisions = {
                c: r for c, r in (old.get("revisions") or {}).items() if c in kept_components
            }

        manifest = {
            "env": env_key,
            "scope": scope,
            "installedAt": time.time(),
            "components": sorted(set(kept_components) | set(components)),
            "revisions": {**kept_revisions, **revisions},
            "files": sorted(set(kept_files) | set(written)),
        }
        try:
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        except OSError as exc:
            raise HarnessError(f"Installed, but could not write {manifest_path}: {exc}") from exc
        legacy = _legacy_manifest_path(env_key, scope)
        if legacy is not None:
            try:
                legacy.unlink()
            except OSError:
                pass

    return {
        "root": str(install_root(env_key, scope, project_path)),
        "written": written,
        "removed": removed,
        "location": location,
    }
