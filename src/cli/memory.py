import os
import json
from pathlib import Path

import questionary
from rich.tree import Tree

from utils.ui import console, QUESTIONARY_STYLE

CONFIG_PATH = Path("~/.mathtools.json").expanduser()

class MemoryManager:
    def __init__(self):
        self.config = self._load_config()

    def _load_config(self) -> dict:
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_config(self) -> None:
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            console.print(f"[dim red]Could not save config: {e}[/]")

    def run_manage_memory(self) -> None:
        console.print("\n[bold bright_magenta]\U0001f9e0  Manage Memory[/]")
        
        vault_path_str = self.config.get("obsidian_vault_path")
        
        if not vault_path_str or not Path(vault_path_str).exists():
            vault_path_str = questionary.path(
                "Enter the path to your Obsidian vault:",
                only_directories=True,
                style=QUESTIONARY_STYLE
            ).ask()
            
            if not vault_path_str:
                return  # user cancelled
                
            self.config["obsidian_vault_path"] = str(Path(vault_path_str).resolve())
            self._save_config()

        vault_path = Path(vault_path_str).resolve()
        
        if not vault_path.exists():
            console.print(f"[bold red]Vault path does not exist:[/] {vault_path}")
            return
            
        console.print(f"\n[bold bright_green]✦ Obsidian Vault:[/] {vault_path}\n")
        
        # Build and print the tree of the vault
        tree = Tree(
            f":open_file_folder: [bold bright_cyan]{vault_path.name}[/]",
            guide_style="bright_blue"
        )
        self._build_tree(vault_path, tree)
        
        console.print(tree)
        console.print()

    def _build_tree(self, current_dir: Path, tree: Tree) -> None:
        ignores = {".obsidian", ".git", ".trash", "node_modules", ".venv", "__pycache__"}
        
        try:
            paths = sorted(current_dir.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            
            for p in paths:
                if p.name in ignores or p.name.startswith("."):
                    continue
                    
                if p.is_dir():
                    branch = tree.add(f":file_folder: [bold bright_blue]{p.name}[/]")
                    self._build_tree(p, branch)
                elif p.suffix == ".md":
                    tree.add(f":page_facing_up: [white]{p.name}[/]")
        except PermissionError:
            tree.add("[red]Permission denied[/]")