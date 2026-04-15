from constants.environments import ENVIRONMENTS
from constants.directories import KNOWN_AI_DIRS
import questionary
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Confirm

from constants.general import VERSION
from utils.ui import console, QUESTIONARY_STYLE


def print_banner() -> None:
    """Print the welcome banner."""
    banner_text = Text()
    banner_text.append("MathTools", style="bold bright_cyan")
    banner_text.append(" AI Development Framework", style="bold white")
    banner_text.append(f"\n\nv{VERSION}", style="dim")

    console.print(
        Panel(
            banner_text,
            title="[bold bright_magenta]✦ MathTools[/]",
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
    console.print(
        Panel(
            "[bold yellow]⚠  No AI framework environments detected.[/]\n\n"
            "None of the following folders exist in your home directory:\n"
            + "\n".join(f"  [dim]{p}[/dim]  ({label})" for p, label in KNOWN_AI_DIRS)
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
            title="🧠  Manage memory",
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