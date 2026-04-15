import requests
import sys

from constants.general import VERSION

from cli.installer import FrameworkInstaller
from cli.memory import MemoryManager
from cli.general import print_banner, prompt_no_environments_found, show_main_menu
from utils.common import detect_environments
from utils.ui import console
from rich.table import Table

def main() -> None:
    installer = FrameworkInstaller()
    memory_manager = MemoryManager()
    try:
        print_banner()

        found = detect_environments()
        if not found:
            proceed = prompt_no_environments_found()
            if not proceed:
                console.print("[dim]Goodbye.[/]")
                sys.exit(0)
            installer.run_installer()
            sys.exit(0)

        from rich import box
        table = Table(
            title="[bold bright_green]✦ Detected Environments[/]",
            show_header=True,
            header_style="bold bright_cyan",
            border_style="bright_green",
            padding=(0, 2),
            box=box.ROUNDED,
        )
        table.add_column("Environment", style="bold white")
        table.add_column("Scope", style="dim")

        for _, label, scope_str in found:
            table.add_row(label, scope_str)
            
        console.print(table)
        console.print()

        action = show_main_menu()

        if action == "install":
            installer.run_installer()
        elif action == "memory":
            memory_manager.run_manage_memory()
        else:
            console.print("[dim]Goodbye.[/]")

    except requests.RequestException as exc:
        console.print(
            f"\n[bold red]✗ Network error:[/] {exc}\n"
            "  Please check your internet connection and try again."
        )
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted by user.[/]")
        sys.exit(130)
    except Exception as exc:
        console.print(f"\n[bold red]✗ Unexpected error:[/] {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
