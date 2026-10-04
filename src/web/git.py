"""Git helpers shared by the project registry and the folder browser."""

import subprocess
from pathlib import Path

# Generous for a local repo, short enough that one wedged repo (a network
# mount, a lock held by another git) cannot stall the 3s dashboard poll.
GIT_TIMEOUT = 5


def run_git(repo: str | Path, *args: str) -> str | None:
    """
    stdout of `git -C repo <args>`, stripped, or None if git fails.

    Never raises: a missing git binary, a timeout and a non-zero exit all read
    as "no answer", so callers just fall back to a default.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def is_git_repo(path: str | Path) -> bool:
    """
    True when `path` is the root of a git working tree.

    Checks for `.git` itself rather than asking `git rev-parse`: that would
    also accept any subfolder of a repo, and a project must be registered at
    its root so its path matches a session's `ProjectPath`. `.git` is a
    directory in a normal clone and a file in a worktree or submodule — both
    count.
    """
    try:
        return (Path(path) / ".git").exists()
    except OSError:
        return False
