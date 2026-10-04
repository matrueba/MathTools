import argparse
import os
import sys

import requests

from constants.general import VERSION

from cli.installer import FrameworkInstaller
from cli.memory import MemoryManager
from cli.general import print_banner, prompt_no_environments_found, show_main_menu
from utils.common import detect_environments
from utils.ui import console
from rich.table import Table
from cli.monitoring.monitoring import MonitoringManager
from web.server import WebDashboard


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mathtools",
        description=f"MathTools AI Development Framework v{VERSION}",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="run the interactive terminal UI instead of the web dashboard",
    )
    return parser.parse_args(argv)


def run_web() -> None:
    """Serve the web dashboard. This is what `mathtools` does by default."""
    print_banner()
    WebDashboard().run_web_dashboard()


def run_cli() -> None:
    """Interactive terminal UI: installer, memory manager and TUI monitoring."""
    installer = FrameworkInstaller()
    memory_manager = MemoryManager()
    monitoring_manager = MonitoringManager()

    print_banner()

    cwd = os.getcwd()
    console.print(f"[dim] Active context:[/] [bold cyan]{cwd}[/]\n")

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
    elif action == "monitoring":
        monitoring_manager.run_monitoring()
    else:
        console.print("[dim]Goodbye.[/]")


def main(argv: list[str] | None = None) -> None:
    """
    Entry point. Web dashboard by default; `--cli` for the terminal UI.

    `argv` defaults to sys.argv[1:] and exists so tests can pick a mode
    without patching sys.argv.
    """
    args = parse_args(argv)

    try:
        if args.cli:
            run_cli()
        else:
            run_web()
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
