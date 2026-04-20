import os
import json
import time
import datetime
import sys
import select
import termios
import tty
from pathlib import Path
from rich.table import Table
from rich import box
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn
from rich.console import Group
from rich.columns import Columns
from rich.live import Live

from utils.ui import console
from constants.source_files import CLAUDE_BASE_DIR, OPENCODE_BASE_DIR, OPENCODE_DB_PATH

from .claude_source import ClaudeSource
from .opencode_source import OpenCodeSource
from .antigravity_source import AntigravitySource

class MonitoringManager:
    def __init__(self):
        self.claude_source = ClaudeSource()
        self.opencode_source = OpenCodeSource()
        self.antigravity_source = AntigravitySource()
        self.cached_totals = {"input": 0, "output": 0, "cacheR": 0, "cacheW": 0}
        self.all_sessions = []
        self.last_update_time = 0
        self.selected_index = 0

    def run_monitoring(self) -> None:
        """Runs the interactive monitoring loop."""
        console.clear()
        self._fetch_data()

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            with Live(self._build_screen(), console=console, screen=False, auto_refresh=False) as live:
                while True:
                    needs_update = False

                    key = self._read_key(fd)
                    if key in ('q', '\x03'):
                        break
                    if key == "\x1b[A":     # Up
                        self.selected_index = max(0, self.selected_index - 1)
                        needs_update = True
                    elif key == "\x1b[B":   # Down
                        self.selected_index = min(
                            len(self.all_sessions) - 1, self.selected_index + 1
                        )
                        needs_update = True
                    elif key == 'r':
                        self._fetch_data()
                        needs_update = True

                    now = time.time()
                    if now - self.last_update_time > 1:
                        self._fetch_data()
                        needs_update = True

                    if needs_update:
                        live.update(self._build_screen())
                        live.refresh()

                    time.sleep(0.05)
        except KeyboardInterrupt:
            pass
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


    def _read_key(self, fd: int) -> str | None:
        """Non-blocking read of a single key (handles arrow escape sequences)."""
        rlist, _, _ = select.select([fd], [], [], 0)
        if not rlist:
            return None
        ch = os.read(fd, 1).decode("utf-8", errors="ignore")
        if ch == '\x1b':
            rlist2, _, _ = select.select([fd], [], [], 0.02)
            if rlist2:
                ch += os.read(fd, 2).decode("utf-8", errors="ignore")
        return ch


    def _fetch_data(self):
        """Fetches fresh data from all sources and updates cache."""
        try:
            claude_sessions, claude_totals = self.claude_source.parse_claude_sessions()
            opencode_sessions, opencode_totals = self.opencode_source.parse_opencode_sessions()
            antigravity_sessions, antigravity_totals = self.antigravity_source.parse_antigravity_sessions()

            self.all_sessions = sorted(
                claude_sessions + opencode_sessions + antigravity_sessions,
                key=lambda x: x["mtime"], reverse=True,
            )
            self.cached_totals = {
                "input":  claude_totals["input"]  + opencode_totals["input"]  + antigravity_totals["input"],
                "output": claude_totals["output"] + opencode_totals["output"] + antigravity_totals["output"],
                "cacheR": claude_totals["cacheR"] + opencode_totals["cacheR"] + antigravity_totals["cacheR"],
                "cacheW": claude_totals["cacheW"] + opencode_totals["cacheW"] + antigravity_totals["cacheW"],
            }
            self.last_update_time = time.time()
        except Exception:
            pass

    def _build_screen(self) -> Group:
        """Assembles the full dashboard layout."""
        ts = os.get_terminal_size()
        total_tokens = sum(self.cached_totals.values())

        def format_k(v: int) -> str:
            if v >= 1_000_000:
                return f"{v/1_000_000:.1f}M"
            elif v >= 1_000:
                return f"{v/1_000:.1f}k"
            return str(v)
            
        # 1. Quota Panel
        quota_text = "[dim]No rate limit data found[/]"
        rate_limits = None
        for s in self.all_sessions:
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
        max_v = max(self.cached_totals.values()) if any(self.cached_totals.values()) else 1
        
        progress.add_task("[yellow]Input", total=max_v, completed=self.cached_totals["input"])
        progress.add_task("[magenta]Output", total=max_v, completed=self.cached_totals["output"])
        progress.add_task("[cyan]CacheR", total=max_v, completed=self.cached_totals["cacheR"])
        progress.add_task("[blue]CacheW", total=max_v, completed=self.cached_totals["cacheW"])
        
        # 3. Sessions Table
        table = Table(
            show_header=True, header_style="bold bright_cyan",
            border_style="bright_blue", box=box.SIMPLE,
            expand=True, padding=(0, 1)
        )
        table.add_column("S", justify="center")
        table.add_column("AI", style="bold yellow")
        table.add_column("Project", style="italic white")
        table.add_column("Session")
        table.add_column("Summary", overflow="ellipsis")
        table.add_column("Status")
        table.add_column("Context")
        table.add_column("Total tokens", justify="right")
        table.add_column("Turn", justify="right")

        active_session = None
        if not self.all_sessions:
            self.selected_index = 0
        else:
            self.selected_index = min(max(0, self.selected_index), len(self.all_sessions) - 1)
            active_session = self.all_sessions[self.selected_index]

            term_h = ts.lines
            body_h = max(5, (term_h - 3) // 3)
            window_size = max(1, body_h - 4)
            start_idx    = max(0, min(self.selected_index - window_size // 2, len(self.all_sessions) - window_size))
            end_idx      = min(len(self.all_sessions), start_idx + window_size)
            visible      = self.all_sessions[start_idx:end_idx]
        
            for i, s in enumerate(visible):
                abs_idx = i + start_idx
                mark  = "[bold green]>[/]" if abs_idx == self.selected_index else " "
                style = "on #222222" if abs_idx == self.selected_index else ""
                
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
                    mark,
                    f"[bold red]*[/]{s['AI']}" if s['Status'] == 'Work' else f"[dim]{s['AI']}[/]",
                    s["Project"],
                    s["SessionId"][:8],
                    trunc_sum,
                    f"[bright_green]● Work[/]" if s['Status'] == 'Work' else f"[yellow]○ Wait[/]",
                    ctx_str,
                    format_k(s.get("TotalTokens", 0)),
                    str(s["TurnCount"])
                )

        # 4. Quota Panel
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
            "[bold cyan][q][/] Back to Menu   [bold yellow][q][/] Quit",
            box=box.MINIMAL,
            padding=(0, 1)
        )

        return Group(
            Panel(header, box=box.ROUNDED),
            top_row,
            Panel(table, title="Sessions", box=box.ROUNDED),
            footer
        )

    

    

