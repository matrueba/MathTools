from constants.environments import ENVIRONMENTS
import questionary
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Confirm

from constants.general import VERSION
from utils.ui import console, QUESTIONARY_STYLE


from rich.align import Align

def print_banner() -> None:
    """Print the welcome banner."""
    ascii_art = r"""
    __  ___          __    __    ______                  __        
   /  |/  / ____ _  / /_  / /_  /_  __/ ____   ____    / /  _____
  / /|_/ / / __ `/ / __/ / __ \  / /   / __ \ / __ \  / /  / ___/
 / /  / / / /_/ / / /_  / / / / / /   / /_/ // /_/ / / /  (__  ) 
/_/  /_/  \__,_/  \__/ /_/ /_/ /_/    \____/ \____/ /_/  /____/  
"""

    banner_text = Text()
    banner_text.append(ascii_art, style="bold bright_cyan")
    banner_text.append("\n  AI Development Framework ", style="bold white")
    banner_text.append(f"v{VERSION}", style="bold bright_magenta")

    console.print(
        Panel(
            Align.center(banner_text),
            title="[bold bright_magenta]✦ Welcome[/]",
            border_style="bright_cyan",
            padding=(1, 4),
        )
    )
    console.print()


def prompt_no_environments_found() -> bool:
    """
    Called when no known AI framework folders are detected.
    Returns True if the user wants to proceed with installation, False to exit.
    """
    env_lines = "\n".join(f"  [dim]{env['global_dir']}[/dim] or [dim]./{env['target_dir']}[/dim]  ({env['label']})" for env in ENVIRONMENTS.values())
    
    console.print(
        Panel(
            "[bold yellow]⚠  No AI framework environments detected.[/]\n\n"
            "None of the following folders exist globally or locally:\n"
            + env_lines
            + "\n\nWould you like to install one now?",
            title="[bold yellow]First-time setup[/]",
            border_style="yellow",
            padding=(1, 3),
        )
    )
    return Confirm.ask("[bold yellow]Install an AI framework now?[/]", default=True)


def show_main_menu() -> str:
    """
    Display the main menu and return the chosen action key.
    Returns one of: 'install', 'memory', 'exit'
    """
    choices = [
        questionary.Choice(
            title="⬇  Install or update AI framework",
            value="install",
        ),
        questionary.Choice(
            title="🧠  Manage Agents Memory",
            value="memory",
        ),
        questionary.Choice(
            title="✕  Exit",
            value="exit",
        ),
    ]

    action = questionary.select(
        "What would you like to do?",
        choices=choices,
        style=QUESTIONARY_STYLE
    ).ask()

    return action or "exit"