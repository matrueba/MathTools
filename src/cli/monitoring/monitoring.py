import os
import json
import time
import datetime
from pathlib import Path
from rich.table import Table
from rich import box
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn
from rich.console import Group
from rich.columns import Columns

from utils.ui import console
from constants.source_files import CLAUDE_BASE_DIR, OPENCODE_BASE_DIR, OPENCODE_DB_PATH

from rich.live import Live
import sys
import select
import termios
import tty

from .claude_source import ClaudeSource
from .opencode_source import OpenCodeSource
from .antigravity_source import AntigravitySource

class MonitoringManager:
    def __init__(self):
        self.claude_source = ClaudeSource()
        self.opencode_source = OpenCodeSource()
        self.antigravity_source = AntigravitySource()


    def run_monitoring(self) -> None:
        """Runs the interactive monitoring loop."""

        console.clear()
        with Live(self._build_screen(), refresh_per_second=1, console=console, screen=False) as live:
            try:
                while True:
                    live.update(self._build_screen())
                    time.sleep(1)
            except KeyboardInterrupt:
                pass

    def _build_screen(self) -> Group:
        """Assembles the full dashboard layout."""
        claude_sessions, claude_totals = self.claude_source.parse_claude_sessions()
        opencode_sessions, opencode_totals = self.opencode_source.parse_opencode_sessions()
        antigravity_sessions, antigravity_totals = self.antigravity_source.parse_antigravity_sessions()
        
        all_sessions = sorted(
            claude_sessions + opencode_sessions + antigravity_sessions, 
            key=lambda x: x["mtime"], reverse=True
        )
        
        global_totals = {
            "input": claude_totals["input"] + opencode_totals["input"] + antigravity_totals["input"],
            "output": claude_totals["output"] + opencode_totals["output"] + antigravity_totals["output"],
            "cacheR": claude_totals["cacheR"] + opencode_totals["cacheR"] + antigravity_totals["cacheR"],
            "cacheW": claude_totals["cacheW"] + opencode_totals["cacheW"] + antigravity_totals["cacheW"],
        }
        
        total_tokens = sum(global_totals.values())
        
        def format_k(v: int) -> str:
            if v >= 1_000_000:
                return f"{v/1_000_000:.1f}M"
            elif v >= 1_000:
                return f"{v/1_000:.1f}k"
            return str(v)
            
        # 1. Quota Panel
        quota_text = "[dim]No rate limit data found[/]"
        rate_limits = None
        for s in all_sessions:
            if s.get("Quota"):
                rate_limits = s["Quota"]
                break
                
        if rate_limits:
            quota_text = "[bold blue]Rate Limits:[/]\n"
            if rate_limits.get("five_hour_pct") is not None:
                quota_text += f"5 Hour: [yellow]{rate_limits['five_hour_pct']:.1f}%[/]\n"
            if rate_limits.get("seven_day_pct") is not None:
                quota_text += f"7 Day: [green]{rate_limits['seven_day_pct']:.1f}%[/]\n"

        # 2. Tokens Panel
        progress = Progress(
            TextColumn("{task.description}", justify="right"),
            BarColumn(bar_width=None),
            TextColumn("{task.completed}"),
            expand=True
        )
        max_v = max(global_totals.values()) if any(global_totals.values()) else 1
        
        progress.add_task("[yellow]Input", total=max_v, completed=global_totals["input"])
        progress.add_task("[magenta]Output", total=max_v, completed=global_totals["output"])
        progress.add_task("[cyan]CacheR", total=max_v, completed=global_totals["cacheR"])
        progress.add_task("[blue]CacheW", total=max_v, completed=global_totals["cacheW"])
        
        # 3. Sessions Table
        table = Table(
            show_header=True, header_style="bold bright_cyan",
            border_style="bright_blue", box=box.SIMPLE,
            expand=True
        )
        table.add_column("AI", style="bold yellow")
        table.add_column("Project", style="italic white")
        table.add_column("Session")
        table.add_column("Summary", overflow="ellipsis")
        table.add_column("Status")
        table.add_column("Model", style="dim")
        table.add_column("Context")
        table.add_column("In", justify="right")
        table.add_column("Out", justify="right")
        table.add_column("CR", justify="right")
        table.add_column("CW", justify="right")
        table.add_column("Total", justify="right")
        table.add_column("Turn", justify="right")
        
        for s in all_sessions:
            ctx_pct = 0
            if s["ContextWindow"] > 0:
                ctx_pct = (s["LastContext"] / s["ContextWindow"]) * 100
            
            # Progress bar simulation for context window
            blocks = "█" * int((ctx_pct / 100) * 10)
            empty = "░" * (10 - len(blocks))
            color = "green" if ctx_pct < 60 else "yellow" if ctx_pct < 85 else "red"
            ctx_str = f"[{color}]{blocks}[/][dim]{empty}[/] {ctx_pct:.0f}%"
 
            summary_text = s["Summary"] if s["Summary"] else "No summary"
            trunc_sum = summary_text[:35] + ("..." if len(summary_text) > 35 else "")
            
            table.add_row(
                f"[bold red]*[/]{s['AI']}" if s['Status'] == 'Work' else f"[dim]{s['AI']}[/]",
                s["Project"],
                s["SessionId"][:8],
                trunc_sum,
                f"[bright_green]● Work[/]" if s['Status'] == 'Work' else f"[yellow]○ Wait[/]",
                s["Model"][:10],
                ctx_str,
                format_k(s.get("InputTokens", 0)),
                format_k(s.get("OutputTokens", 0)),
                format_k(s.get("CacheR", 0)),
                format_k(s.get("CacheW", 0)),
                format_k(s.get("TotalTokens", 0)),
                str(s["TurnCount"])
            )

        # Build final screen
        console_width = console.width if console.width else 100
        top_row = Columns([
            Panel(quota_text, title="Quota (latest)", box=box.ROUNDED, width=int(console_width * 0.3)),
            Panel(Group(f"Total: {format_k(total_tokens)}", progress), title="Tokens", box=box.ROUNDED, width=int(console_width * 0.65))
        ])
        
        now = datetime.datetime.now().strftime("%H:%M:%S")
        header = Columns([
            "[bold bright_magenta]📊 Agent Monitor[/]",
            f"[dim]Last Update: {now}[/]"
        ], expand=True)

        footer = Panel(
            "[bold cyan][q][/] Back to Menu   [bold yellow][Ctrl+C][/] Force Quit",
            box=box.MINIMAL,
            padding=(0, 1)
        )

        return Group(
            Panel(header, box=box.ROUNDED),
            top_row,
            Panel(table, title="Sessions", box=box.ROUNDED),
            footer
        )

    

    

