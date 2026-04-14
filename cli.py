#!/usr/bin/env python3
"""
MathTools – CLI
==================================================
Downloads and installs AI development tool-sets from GitHub,
letting the user choose which IDE/agent environments to set up.
"""

import io
import os
import shutil
import sys
import tempfile
import zipfile

from environments import ENVIRONMENTS

import requests
import questionary
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TransferSpeedColumn,
)
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt, Confirm

# ── Constants ────────────────────────────────────────────────────────────────

REPOSITORIES = {
    "framework": {
        "url": "https://github.com/matrueba/matrueba-AI-development-framework/archive/refs/heads/main.zip",
        "prefix": "matrueba-AI-development-framework-main/"
    },
    "skills": {
        "url": "https://github.com/matrueba/matrueba-skills-framework/archive/refs/heads/main.zip",
        "prefix": "matrueba-skills-framework-main/"
    }
}

VERSION = "0.1.0"

# ── Environment Definitions ─────────────────────────────────────────────────
# Each environment maps to:
#   target_dir  → the dot-folder that will be created in the user's project
#   sources     → list of (src_path_in_zip, dest_subpath) tuples
#                 src_path_in_zip is relative to the ZIP root
#                 dest_subpath is relative to target_dir
#
# Shared content (skills) lives under .agents/skills and .gemini/skills in the
# repo (they are identical).  We always pull from .agents/skills as canonical
# source and place it where each environment expects it.



console = Console()


def print_banner() -> None:
    """Print the welcome banner."""
    banner_text = Text()
    banner_text.append("MathTools", style="bold bright_cyan")
    banner_text.append(" AI Development Framework", style="bold white")
    banner_text.append(f"\n\nv{VERSION}", style="dim")

    console.print(
        Panel(
            banner_text,
            title="[bold bright_magenta]✦ Installer[/]",
            border_style="bright_cyan",
            padding=(1, 4),
        )
    )
    console.print()


def show_environments_menu() -> list[str]:
    """Display an interactive menu and return the list of chosen environment keys."""
    table = Table(
        title="[bold]Available Environments[/bold]",
        show_header=True,
        header_style="bold bright_cyan",
        border_style="bright_cyan",
        padding=(0, 2),
    )
    table.add_column("Environment", style="bold white")
    table.add_column("Description", style="dim")

    env_keys = list(ENVIRONMENTS.keys())
    for key in env_keys:
        env = ENVIRONMENTS[key]
        table.add_row(env["label"], env["description"])

    console.print(table)
    console.print()

    choices = [questionary.Choice(title=ENVIRONMENTS[k]["label"], value=k, checked=False) for k in env_keys]
    
    selected = questionary.checkbox(
        "Select the environments to install:",
        choices=choices,
        instruction=" (Space = seleccionar, 'a' = alternar/limpiar todo, Enter = confirmar)",
        style=questionary.Style([
            ('qmark', 'fg:#00ffff bold'),
            ('question', 'bold'),
            ('pointer', 'fg:#ff00ff bold'),
            ('highlighted', 'fg:#ff00ff bold'),
            ('selected', 'fg:#00ff00'),
        ])
    ).ask()
    
    if not selected:
        console.print("[bold red]You must select at least one environment. Cancelling.[/]")
        sys.exit(0)
        
    return selected


def download_repos_zips() -> dict[str, bytes]:
    """Download the repositories ZIPs and return the raw bytes."""
    repo_bytes = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40),
        DownloadColumn(),
        TransferSpeedColumn(),
        console=console,
    ) as progress:
        
        for repo_name, repo_info in REPOSITORIES.items():
            url = repo_info["url"]
            console.print(f"[bold bright_cyan]⬇  Downloading {repo_name} from GitHub...[/]\n   [dim]{url}[/dim]\n")
            
            task = progress.add_task(f"Downloading {repo_name}", total=None)

            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()

            total = response.headers.get("content-length")
            if total is not None:
                progress.update(task, total=int(total))

            chunks: list[bytes] = []
            for chunk in response.iter_content(chunk_size=8192):
                chunks.append(chunk)
                progress.advance(task, len(chunk))
                
            repo_bytes[repo_name] = b"".join(chunks)
            console.print(f"[bold green]✓ {repo_name} download complete.[/]\n")

    return repo_bytes


def get_available_items(zips_bytes: dict[str, bytes], repo_name: str, src_path: str) -> list[str]:
    """Return a list of top-level item names in the given src_path inside the ZIP."""
    prefix = REPOSITORIES[repo_name]["prefix"] + src_path
    if not prefix.endswith("/"):
        prefix += "/"

    items = set()
    with zipfile.ZipFile(io.BytesIO(zips_bytes[repo_name])) as zf:
        for member in zf.namelist():
            if not member.startswith(prefix) or member == prefix:
                continue
            relative = member[len(prefix) :]
            item_name = relative.split("/")[0]
            if item_name:
                items.add(item_name)
    return sorted(list(items))


def gather_selections(zips_bytes: dict[str, bytes], selected_envs: list[str]) -> dict:
    """Ask the user whether to install all or selected items for each source."""
    selections: dict = {}
    for env_key in selected_envs:
        env = ENVIRONMENTS[env_key]
        selections[env_key] = {}
        console.print(f"\n[bold bright_magenta]✦ Configuration for {env['label']}[/]")
        
        for repo_name, src_path, dest_subpath in env["sources"]:
            items = get_available_items(zips_bytes, repo_name, src_path)
            if not items:
                selections[env_key][src_path] = "all"
                continue
                
            source_title = dest_subpath.capitalize()

            # Ask if they want all
            install_all = questionary.confirm(
                f"Install all available {source_title}?",
                default=True,
                style=questionary.Style([('question', 'bold')])
            ).ask()
            
            if install_all:
                selections[env_key][src_path] = "all"
            else:
                choices = [questionary.Choice(title=item, value=item, checked=False) for item in items]
                selected_items = questionary.checkbox(
                    f"Select specific {source_title} to install:",
                    choices=choices,
                    instruction=" (Space = seleccionar, 'a' = alternar/limpiar todo, Enter = confirmar)",
                    style=questionary.Style([
                        ('qmark', 'fg:#00ffff bold'),
                        ('question', 'bold'),
                        ('pointer', 'fg:#ff00ff bold'),
                        ('highlighted', 'fg:#ff00ff bold'),
                        ('selected', 'fg:#00ff00'),
                    ])
                ).ask()
                
                if not selected_items:
                    console.print(f"[bold yellow]No {source_title} selected. Skipping.[/]")
                    selections[env_key][src_path] = []
                else:
                    selections[env_key][src_path] = selected_items
                
    return selections


def extract_environment(
    zips_bytes: dict[str, bytes],
    env_key: str,
    dest_root: str,
    env_selections: dict,
) -> list[str]:
    """
    Extract the files that belong to *env_key* from the ZIP into *dest_root*.

    Returns a list of relative paths that were written.
    """
    env = ENVIRONMENTS[env_key]
    target_dir = os.path.join(dest_root, env["target_dir"])
    written: list[str] = []

    for repo_name, src_path, dest_subpath in env["sources"]:
        prefix = REPOSITORIES[repo_name]["prefix"] + src_path
        if not prefix.endswith("/"):
            prefix += "/"

        selection = env_selections.get(src_path, "all")

        with zipfile.ZipFile(io.BytesIO(zips_bytes[repo_name])) as zf:
            for member in zf.namelist():
                if not member.startswith(prefix):
                    continue
                # Skip directory entries
                if member.endswith("/"):
                    continue

                relative = member[len(prefix) :]

                # Check selection
                if selection != "all":
                    item_name = relative.split("/")[0]
                    if item_name not in selection:
                        continue

                out_path = os.path.join(target_dir, dest_subpath, relative)
                os.makedirs(os.path.dirname(out_path), exist_ok=True)

                with zf.open(member) as src, open(out_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)

                # Nice relative path for the summary
                written.append(
                    os.path.join(env["target_dir"], dest_subpath, relative)
                )

    return written


def print_summary(results: dict[str, list[str]]) -> None:
    """Print a final summary table of everything installed."""
    console.print()

    table = Table(
        title="[bold bright_green]✦ Installation Summary[/]",
        show_header=True,
        header_style="bold bright_cyan",
        border_style="bright_green",
        padding=(0, 2),
    )
    table.add_column("Environment", style="bold white", min_width=20)
    table.add_column("Files", style="dim", justify="right", width=8)
    table.add_column("Target folder", style="bright_yellow")

    total_files = 0
    for env_key, files in results.items():
        env = ENVIRONMENTS[env_key]
        table.add_row(env["label"], str(len(files)), env["target_dir"])
        total_files += len(files)

    console.print(table)
    console.print(
        f"\n[bold bright_green]✓ Done![/] "
        f"[bold]{total_files}[/bold] files installed across "
        f"[bold]{len(results)}[/bold] environment(s).\n"
    )


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    """Entry-point for the CLI."""
    try:
        print_banner()

        selected = show_environments_menu()

        # Confirm selection
        labels = ", ".join(ENVIRONMENTS[k]["label"] for k in selected)
        console.print(
            f"\n[bold]Environments selected:[/] [bright_cyan]{labels}[/]\n"
        )
        if not Confirm.ask("[bold]Proceed with installation?[/]", default=True):
            console.print("[dim]Installation cancelled.[/]")
            raise SystemExit(0)

        # Check for existing folders
        cwd = os.getcwd()
        existing = [
            ENVIRONMENTS[k]["target_dir"]
            for k in selected
            if os.path.exists(os.path.join(cwd, ENVIRONMENTS[k]["target_dir"]))
        ]
        if existing:
            console.print(
                f"\n[bold yellow]⚠  The following folders already exist:[/] "
                f"{', '.join(existing)}"
            )
            if not Confirm.ask(
                "[bold yellow]Overwrite existing files?[/]", default=False
            ):
                console.print("[dim]Installation cancelled.[/]")
                raise SystemExit(0)

        # Download
        zips_bytes = download_repos_zips()

        # Ask user for specific components
        selections = gather_selections(zips_bytes, selected)

        # Extract
        results: dict[str, list[str]] = {}
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=40),
            console=console,
        ) as progress:
            task = progress.add_task(
                "Installing environments", total=len(selected)
            )
            for env_key in selected:
                progress.update(
                    task,
                    description=f"Installing [bold]{ENVIRONMENTS[env_key]['label']}[/]",
                )
                written = extract_environment(zips_bytes, env_key, cwd, selections[env_key])
                results[env_key] = written
                progress.advance(task)

        print_summary(results)

    except requests.RequestException as exc:
        console.print(
            f"\n[bold red]✗ Network error:[/] {exc}\n"
            "  Please check your internet connection and try again."
        )
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted by user.[/]")
        sys.exit(130)
    except SystemExit:
        raise
    except Exception as exc:
        console.print(f"\n[bold red]✗ Unexpected error:[/] {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
