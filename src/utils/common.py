import os

from constants.environments import ENVIRONMENTS
    
def detect_environments() -> list[tuple[str, str, str]]:
    """Return a list of (env_key, label, scope_str) for every AI framework folder found locally or globally."""
    found = []
    
    for key, env in ENVIRONMENTS.items():
        global_path = os.path.expanduser(env["global_dir"])
        local_path = os.path.join(os.getcwd(), env["target_dir"])
        
        global_exists = os.path.isdir(global_path)
        local_exists = os.path.isdir(local_path)
        
        if global_exists or local_exists:
            scopes = []
            if local_exists:
                scopes.append("local")
            if global_exists:
                scopes.append("global")
                
            scope_str = " / ".join(scopes)
            found.append((key, env["label"], scope_str))
            
    return found