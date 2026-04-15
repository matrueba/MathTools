import os

from constants.directories import KNOWN_AI_DIRS
    
def detect_environments() -> list[tuple[str, str]]:
    """Return a list of (path, label) for every known AI framework folder found in HOME."""
    found = []
    for raw_path, label in KNOWN_AI_DIRS:
        expanded = os.path.expanduser(raw_path)
        if os.path.isdir(expanded):
            found.append((raw_path, label))
    return found