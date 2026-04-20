import os
import time
import datetime
import sys
import threading
import termios
import tty
import queue

from rich.table import Table
from rich import box
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn
from rich.console import Group
from rich.columns import Columns
from rich.live import Live
from rich.layout import Layout

from utils.ui import console
from constants.source_files import CLAUDE_BASE_DIR, OPENCODE_BASE_DIR, OPENCODE_DB_PATH

from .claude_source import ClaudeSource
from .opencode_source import OpenCodeSource
from .antigravity_source import AntigravitySource
from .extend import render_extended_session


class MonitoringManager:
    def __init__(self):
        self.claude_source = ClaudeSource()
        self.opencode_source = OpenCodeSource()
        self.antigravity_source = AntigravitySource()
        self.selected_index = 0
        self.all_sessions = []
        self.cached_totals = {"input": 0, "output": 0, "cacheR": 0, "cacheW": 0}
        self.last_update_time = 0
        self._key_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._term_size  = (0, 0)   # (columns, lines) — detecta resize

        self._term_size  = (0, 0)   # Track resize


    def _input_thread(self):
        """Dedicated thread: reads stdin in raw mode and feeds keys to queue."""
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while not self._stop_event.is_set():
                # Block for up to 50 ms so we can check the stop flag
                import select as _select
                rlist, _, _ = _select.select([sys.stdin], [], [], 0.05)
                if rlist:
                    ch = sys.stdin.read(1)
                    if ch == '\x1b':
                        rlist2, _, _ = _select.select([sys.stdin], [], [], 0.02)
                        if rlist2:
                            ch += sys.stdin.read(2)
                    self._key_queue.put(ch)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


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



    def _render_dashboard(self):
        """Builds the dashboard as a manual Group/Table (no Layout)."""
        ts = os.get_terminal_size()
        self._term_size = (ts.columns, ts.lines)
        
        total_tokens = sum(self.cached_totals.values())

        def format_k(v: int) -> str:
            if v >= 1_000_000: return f"{v/1_000_000:.1f}M"
            if v >= 1_000:     return f"{v/1_000:.1f}k"
            return str(v)

        quota_text = "[dim]N/A[/]"
        for s in self.all_sessions:
            if s.get("Quota"):
                rl = s["Quota"]
                parts = []
                if rl.get("five_hour_pct") is not None:
                    parts.append(f"5H:[yellow]{rl['five_hour_pct']:.0f}%[/]")
                if rl.get("seven_day_pct") is not None:
                    parts.append(f"7D:[green]{rl['seven_day_pct']:.0f}%[/]")
                quota_text = " ".join(parts)
                break

        now = datetime.datetime.now().strftime("%H:%M:%S")
        header_line = (
            f"[bold magenta]📊 FLEET[/]  {quota_text}  "
            f"[dim]| {now} | [↑/↓] Nav [q] Exit[/]"
        )

        top_panel = Panel(Group(
            header_line,
            f"[dim]Total: {format_k(total_tokens)}[/]"
        ), height=3)

        # # 2. SESSION TABLE
        # table = Table(
        #     show_header=True, header_style="bold cyan",
        #     border_style="blue", box=box.SIMPLE, expand=True, padding=(0, 1),
        # )
        # table.add_column("S",       width=2,  justify="center")
        # table.add_column("AI",      width=3,  style="bold yellow")
        # table.add_column("Project", width=10, style="italic white")
        # table.add_column("Session", width=6)
        # table.add_column("Summary", ratio=1,  no_wrap=True)
        # table.add_column("Status",  width=6)
        # table.add_column("Total",   width=7,  justify="right")

        # active_session = None
        # if not self.all_sessions:
        #     self.selected_index = 0
        # else:
        #     self.selected_index = min(max(0, self.selected_index), len(self.all_sessions) - 1)
        #     active_session = self.all_sessions[self.selected_index]

        #     # Calculamos tamaño dinámico para el body
        #     term_h = ts.lines
        #     body_h = max(5, (term_h - 3) // 3)
        #     window_size = max(1, body_h - 4)

        #     start_idx    = max(0, min(self.selected_index - window_size // 2, len(self.all_sessions) - window_size))
        #     end_idx      = min(len(self.all_sessions), start_idx + window_size)
        #     visible      = self.all_sessions[start_idx:end_idx]

        #     for i, s in enumerate(visible):
        #         abs_idx = i + start_idx
        #         mark  = "[bold cyan]>[/]" if abs_idx == self.selected_index else " "
        #         style = "on #222222" if abs_idx == self.selected_index else ""
        #         table.add_row(
        #             mark, s["AI"], s["Project"][:10], s["SessionId"][:6],
        #             s.get("Summary", "")[:55],
        #             "[green]WORK[/]" if s["Status"] == "Work" else "[yellow]WAIT[/]",
        #             format_k(s.get("TotalTokens", 0)),
        #             style=style,
        #         )

        # body_panel = Panel(Group("[bold blue]Active Sessions[/]", table), height=body_h)

        # # 3. DETAILS
        # details_h = max(1, ts.lines - 3 - body_h)
        # try:
        #     details_renderable = render_extended_session(active_session)
        # except Exception:
        #     details_renderable = "[dim]No session selected[/]"
        
        # details_panel = Panel(details_renderable, height=details_h)

        return Group(top_panel)

    # -------------------------------------------------------------------------
    # Main loop
    # -------------------------------------------------------------------------
    def run_monitoring(self) -> None:
        """Runs the interactive monitoring loop (auto_refresh=False)."""
        if not sys.stdin.isatty():
            return

        self._fetch_data()

        # Start the keyboard input thread
        inp_thread = threading.Thread(target=self._input_thread, daemon=True)
        inp_thread.start()

        try:
            with Live(
                self._render_dashboard(),
                console=console,
                screen=True,
                auto_refresh=False,
            ) as live:
                while True:
                    needs_update = False

                    # Drain all pending keys
                    while True:
                        try:
                            key = self._key_queue.get_nowait()
                        except queue.Empty:
                            break

                        if key in ('q', '\x03'):
                            return

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

                    # Periodic data refresh (every 5 s)
                    now = time.time()
                    if now - self.last_update_time > 5:
                        self._fetch_data()
                        needs_update = True

                    # Detectar resize
                    ts = os.get_terminal_size()
                    resized = (ts.columns, ts.lines) != self._term_size

                    if needs_update or resized:
                        live.update(self._render_dashboard())
                        live.refresh()

                    time.sleep(0.05)

        except KeyboardInterrupt:
            pass
        finally:
            self._stop_event.set()
            inp_thread.join(timeout=1)
