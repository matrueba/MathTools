import os
from constants.environments import ENVIRONMENTS
import questionary
from utils.ui import QUESTIONARY_STYLE

class InstallerUtils:

    @staticmethod
    def get_modes(selected: list[str]) -> dict[str, str]:
        modes = {}
        for k in selected:
            mode = questionary.select(
            f"Install {ENVIRONMENTS[k]['label']} in the current repository or globally?",
            choices=[
                questionary.Choice("Local (current repository)", value="local"),
                questionary.Choice("Global (~/)", value="global")
            ],
            style=QUESTIONARY_STYLE
            ).ask()
            if not mode:
                return
            modes[k] = mode
        return modes

    @staticmethod
    def get_existing_folders(selected: list[str], modes: dict[str, str]) -> list[str]:
        existing = []
        cwd = os.getcwd()
        for k in selected:
            env = ENVIRONMENTS[k]
            if modes[k] == "local":
                path = os.path.join(cwd, env["target_dir"])
                if os.path.exists(path):
                    existing.append(env["target_dir"])
            else:
                for _, _, _, global_path in env["sources"]:
                    path = os.path.expanduser(global_path)
                    if os.path.exists(path):
                        existing.append(global_path)
        return existing


