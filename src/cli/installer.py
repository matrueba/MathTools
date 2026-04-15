
from constants.environments import ENVIRONMENTS
from constants.repositories import REPOSITORIES
from utils.installer_utils import InstallerUtils

import io
import os
import shutil
import sys
import zipfile

import requests
import questionary
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
from rich.prompt import Confirm

from constants.general import VERSION
from utils.ui import console, QUESTIONARY_STYLE

class FrameworkInstaller:
    def __init__(self):
        self.installerUtils = InstallerUtils()
        self.selected_modes: dict[str, str] = {}
        self.existing_folders: list[str] = []
        self.selected_envs: list[str] = []
        self.selections: dict = {}
        self.results: dict[str, tuple[list[str], str]] = {}
        

    def run_installer(self) -> None:
        """Run the full AI framework installer flow."""
        self.selected_envs = self.show_environments_menu()

        labels = ", ".join(ENVIRONMENTS[k]["label"] for k in self.selected_envs)
        console.print(
            f"\n[bold]Environments selected:[/] [bright_cyan]{labels}[/]\n"
        )
        if not Confirm.ask("[bold]Proceed with installation?[/]", default=True):
            console.print("[dim]Installation cancelled.[/]")
            return

        self.selected_modes = self.installerUtils.get_modes(self.selected_envs)
        self.existing_folders = self.installerUtils.get_existing_folders(self.selected_envs, self.selected_modes)

        if self.existing_folders:
            self.existing_folders = sorted(list(set(self.existing_folders)))
            console.print(
                f"\n[bold yellow]⚠  The following folders already exist:[/] "
                f"{', '.join(self.existing_folders)}"
            )
            if not Confirm.ask(
                "[bold yell ow]Overwrite existing files?[/]", default=False
            ):
                console.print("[dim]Installation cancelled.[/]")
                return

        zips_bytes = self.download_repos_zips()
        self.gather_selections(zips_bytes)
        self.print_progress(zips_bytes)
        self.print_summary()


    @staticmethod
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


    def gather_selections(self, zips_bytes: dict[str, bytes]) -> dict:
        """Ask the user whether to install all or selected items for each source."""
        for env_key in self.selected_envs:
            env = ENVIRONMENTS[env_key]
            self.selections[env_key] = {}
            console.print(f"\n[bold bright_magenta]✦ Component Selection for {env['label']}[/]")
            for repo_name, src_path, dest_subpath, global_path in env["sources"]:
                items = self.get_available_items(zips_bytes, repo_name, src_path)
                if not items:
                    self.selections[env_key][src_path] = "all"
                    continue
                    
                source_title = dest_subpath.capitalize()

                install_all = questionary.confirm(
                    f"Install all available {source_title}?",
                    default=True,
                    style=questionary.Style([('question', 'bold')])
                ).ask()
                
                if install_all:
                    self.selections[env_key][src_path] = "all"
                else:
                    choices = [questionary.Choice(title=item, value=item, checked=False) for item in items]
                    selected_items = questionary.checkbox(
                        f"Select specific {source_title} to install:",
                        choices=choices,
                        instruction=" (Space = select/deselect, 'a' = select/deselect all, Enter = confirm)",
                        style=QUESTIONARY_STYLE
                    ).ask()
                    
                    if not selected_items:
                        console.print(f"[bold yellow]No {source_title} selected. Skipping.[/]")
                        self.selections[env_key][src_path] 
                    else:
                        self.selections[env_key][src_path] = selected_items
                    


    @staticmethod
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
            instruction=" (Space = select/deselect, 'a' = select/deselect all, Enter = confirm)",
            style=QUESTIONARY_STYLE
        ).ask()
        
        if not selected:
            console.print("[bold red]You must select at least one environment. Cancelling.[/]")
            sys.exit(0)
            
        return selected


    def print_summary(self) -> None:
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
        table.add_column("Location", style="bright_yellow")

        total_files = 0
        for env_key, (files, location) in self.results.items():
            env = ENVIRONMENTS[env_key]
            table.add_row(env["label"], str(len(files)), location)
            total_files += len(files)

        console.print(table)
        console.print(
            f"\n[bold bright_green]✓ Done![/] "
            f"[bold]{total_files}[/bold] files installed across "
            f"[bold]{len(self.results)}[/bold] environment(s).\n"
        )

    def print_progress(self, zips_bytes: dict[str, bytes]) -> None:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=40),
            console=console,
        ) as progress:
            task = progress.add_task(
                "Installing environments", total=len(self.selected_envs)
            )
            for env_key in self.selected_envs:
                progress.update(
                    task,
                    description=f"Installing [bold]{ENVIRONMENTS[env_key]['label']}[/]",
                )
                written, location = self.extract_environment(zips_bytes, env_key)
                self.results[env_key] = (written, location)
                progress.advance(task)


    def extract_environment(self, zips_bytes: dict[str, bytes], env_key: str) -> tuple[list[str], str]:
        """
        Extract the files that belong to *env_key* from the ZIP into *dest_root* or globally.

        Returns a tuple of (written_files_list, target_base_path).
        """
        env = ENVIRONMENTS[env_key]
        mode = self.selected_modes[env_key]
        dest_root = os.getcwd() if mode == "local" else os.path.expanduser("~")
        target_dir = os.path.join(dest_root, env["target_dir"])
        written: list[str] = []

        for repo_name, src_path, dest_subpath, global_path in env["sources"]:
            prefix = REPOSITORIES[repo_name]["prefix"] + src_path
            if not prefix.endswith("/"):
                prefix += "/"

            selection = self.selections[env_key].get(src_path, "all")

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

                    if mode == "global":
                        out_base_dir = os.path.expanduser(global_path)
                        out_path = os.path.join(out_base_dir, relative)
                        written.append(os.path.join(global_path, relative))
                    else:
                        out_base_dir = os.path.join(target_dir, dest_subpath)
                        out_path = os.path.join(out_base_dir, relative)
                        written.append(os.path.join(env["target_dir"], dest_subpath, relative))

                    os.makedirs(os.path.dirname(out_path), exist_ok=True)

                    with zf.open(member) as src, open(out_path, "wb") as dst:
                        shutil.copyfileobj(src, dst)

        return written, "Global (~/)" if mode == "global" else env["target_dir"]


    @staticmethod
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
        
