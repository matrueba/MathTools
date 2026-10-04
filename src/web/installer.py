"""
Harness installer: the non-interactive core of the old CLI installer.

Two data tables drive it and there is no per-environment code: ENVIRONMENTS
says which (repo, path in zip, destination) tuples make up each agent's
harness, REPOSITORIES where each repo's archive lives and the prefix GitHub
prepends inside it. To support a new agent, add an ENVIRONMENTS entry.

Each repo's zip is downloaded once into memory and the same bytes serve both
listing what can be installed (`get_available_items`) and writing it
(`extract_environment`). Nothing here prompts or prints; choosing scope and
components is the caller's job (the harness endpoint, once it stops being a
simulation).
"""

import io
import os
import shutil
import zipfile

import requests

from constants.environments import ENVIRONMENTS
from constants.repositories import REPOSITORIES

DOWNLOAD_TIMEOUT_SECONDS = 60


def download_repo_zips() -> dict[str, bytes]:
    """Every repository archive in REPOSITORIES, as raw bytes keyed by name."""
    zips = {}
    for repo_name, repo_info in REPOSITORIES.items():
        response = requests.get(repo_info["url"], timeout=DOWNLOAD_TIMEOUT_SECONDS)
        response.raise_for_status()
        zips[repo_name] = response.content
    return zips


def _zip_prefix(repo_name: str, src_path: str) -> str:
    prefix = REPOSITORIES[repo_name]["prefix"] + src_path
    return prefix if prefix.endswith("/") else prefix + "/"


def get_available_items(zips: dict[str, bytes], repo_name: str, src_path: str) -> list[str]:
    """Top-level item names under `src_path` in one repo's zip, sorted."""
    prefix = _zip_prefix(repo_name, src_path)
    items = set()
    with zipfile.ZipFile(io.BytesIO(zips[repo_name])) as zf:
        for member in zf.namelist():
            if not member.startswith(prefix) or member == prefix:
                continue
            item_name = member[len(prefix):].split("/")[0]
            if item_name:
                items.add(item_name)
    return sorted(items)


def get_existing_folders(env_keys: list[str], modes: dict[str, str], cwd: str) -> list[str]:
    """
    Install destinations that already exist, i.e. what an install would overwrite.

    `modes` maps each env key to "local" (under `cwd`) or "global" (under ~).
    """
    existing = []
    for key in env_keys:
        env = ENVIRONMENTS[key]
        if modes[key] == "local":
            if os.path.exists(os.path.join(cwd, env["target_dir"])):
                existing.append(env["target_dir"])
        else:
            for _, _, _, global_path in env["sources"]:
                if os.path.exists(os.path.expanduser(global_path)):
                    existing.append(global_path)
    return sorted(set(existing))


def extract_environment(
    zips: dict[str, bytes],
    env_key: str,
    mode: str,
    selections: dict[str, str | list[str]],
    cwd: str,
) -> tuple[list[str], str]:
    """
    Write one environment's harness to disk.

    `selections` maps each source's `src_path` to "all" or a list of
    top-level item names; a source missing from it installs everything.
    Local mode writes `<cwd>/<target_dir>/<dest_subpath>/…`, global mode the
    source's expanded `global_path` — the two produce different directory
    shapes, which is why ENVIRONMENTS carries both.

    Returns (written paths, as shown to the user; a label for the location).
    """
    env = ENVIRONMENTS[env_key]
    target_dir = os.path.join(cwd, env["target_dir"])
    written: list[str] = []

    for repo_name, src_path, dest_subpath, global_path in env["sources"]:
        prefix = _zip_prefix(repo_name, src_path)
        selection = selections.get(src_path, "all")

        with zipfile.ZipFile(io.BytesIO(zips[repo_name])) as zf:
            for member in zf.namelist():
                if not member.startswith(prefix) or member.endswith("/"):
                    continue

                relative = member[len(prefix):]
                if selection != "all" and relative.split("/")[0] not in selection:
                    continue

                if mode == "global":
                    out_path = os.path.join(os.path.expanduser(global_path), relative)
                    written.append(os.path.join(global_path, relative))
                else:
                    out_path = os.path.join(target_dir, dest_subpath, relative)
                    written.append(os.path.join(env["target_dir"], dest_subpath, relative))

                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                with zf.open(member) as src, open(out_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)

    return written, "Global (~/)" if mode == "global" else env["target_dir"]
