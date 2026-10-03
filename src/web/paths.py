"""Filesystem paths shared by the web backend."""

from pathlib import Path


def repo_root() -> Path:
    """
    Repo root, found by walking up from this file to the pyproject.toml.

    Deliberately not a fixed `parents[N]`: this package has already moved once
    (src/cli/web → src/web), and a hardcoded depth breaks *silently* — the API
    keeps answering while the frontend mount quietly disappears, so no test
    that only calls /api/* would notice.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file():
            return parent

    # Installed outside a source checkout: fall back to the package's parent.
    return here.parents[2]
