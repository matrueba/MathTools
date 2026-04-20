import time
from rich.console import Group
from rich.text import Text
from rich.rule import Rule
from rich.table import Table
from rich.columns import Columns

def render_extended_session(session):
    """Redesigned extended view with two columns: CHILDREN and SUBAGENTS."""
    if not session:
        return Group(
            Rule(style="blue"),
            "[dim]  No session selected — use ↑/↓ to navigate[/]",
        )

    def format_k(v: int) -> str:
        if v >= 1_000_000: return f"{v/1_000_000:.1f}M"
        if v >= 1_000:     return f"{v/1_000:.1f}k"
        return str(v)

    # Status badge
    status_style = "green" if session.get("Status") == "Work" else "yellow"
    status_label = f"[{status_style}]{session.get('Status', '?').upper()}[/]"

    # Line 1 — session header
    sid   = session["SessionId"][:12]
    path  = session.get("ProjectPath", "?")
    if path != "?":
        # Shorten only if very long, keep meaningful parts
        if len(path) > 40:
            path = "..." + path[-37:]
    
    ai    = session.get("AI", "?")
    status_style = "green" if session.get("Status") == "Work" else "yellow"
    status_icon = "●" if session.get("Status") == "Work" else "○"
    
    header = Text.assemble(
        ("SESSION ", "bold bright_white"),
        (f"(▶{sid} · {path})", "dim"),
    )
    
    summary = session.get("Summary", "No task active")
    task_line = Text.assemble(
        ("  task ", "dim"),
        (summary, "white"),
    )

    # 2. Two Columns: CHILDREN | SUBAGENTS
    
    # CHILDREN Table
    child_table = Table(box=None, padding=(0, 1), show_header=True, header_style="bold bright_white")
    child_table.add_column("CHILDREN", ratio=1)
    child_table.add_row("[bold]PID[/]  [dim]command[/] [cyan]mem[/] [magenta]cpu[/]")
    
    # Helper for real process info
    def _get_proc_info(pid_val):
        if not pid_val: return "?", "0.0%", "0M"
        try:
            import subprocess
            # Use ps to get command, cpu and rss
            cmd = ["ps", "-p", str(pid_val), "-o", "comm,%cpu,rss", "--no-headers"]
            out = subprocess.check_output(cmd).decode().strip()
            if out:
                parts = out.split()
                if len(parts) >= 3:
                    comm = parts[0]
                    cpu = parts[1]
                    rss_val = int(parts[2])
                    
                    if rss_val > 1024*1024: mem_f = f"{rss_val/(1024*1024):.1f}G"
                    elif rss_val > 1024:    mem_f = f"{rss_val/1024:.1f}M"
                    else:                    mem_f = f"{rss_val}K"
                    return comm, f"{cpu}%", mem_f
        except: pass
        return "?", "0.0%", "0M"

    pids = session.get("PIDs", [])
    if not pids:
        child_table.add_row("[dim]  (No active processes)[/]")
    else:
        for pid in pids:
            comm, cpu, mem = _get_proc_info(pid)
            child_table.add_row(f"[bold]{pid}[/] [dim]{comm[:20]}[/] [cyan]{mem}[/] [magenta]{cpu}[/]")

    # SUBAGENTS Table
    sub_table = Table(box=None, padding=(0, 1), show_header=True, header_style="bold bright_white")
    sub_table.add_column("SUBAGENTS", ratio=1)
    
    subagents = session.get("Subagents", [])
    if not subagents:
        sub_table.add_row("[dim] (No subtasks registered)[/]")
    else:
        for s in subagents:
            icon = "[green]✓[/]" if s["status"] == "done" else "[white]●[/]" if s["status"] == "work" else "[dim]○[/]"
            sub_table.add_row(f"{icon} {s['label'][:40]}")

    columns = Columns([child_table, sub_table], expand=True)

    # 3. Footer (Metrics)
    mtime = time.strftime("%H:%M:%S", time.localtime(session.get("mtime", 0)))
    turns = session.get("TurnCount", "-")
    model = session.get("Model", "-")
    ctx_pct = 0.0
    if session.get("ContextWindow", 0) > 0:
        ctx_pct = (session.get("LastContext", 0) / session["ContextWindow"]) * 100
    color  = "green" if ctx_pct < 60 else ("yellow" if ctx_pct < 85 else "red")
    filled = int((ctx_pct / 100) * 24)
    bar    = f"[{color}]{'█' * filled}[/][dim]{'░' * (24 - filled)}[/]"
    context_line  = f"  [dim]Context[/] {bar} [bold]{ctx_pct:.1f}%[/]"
    inp   = format_k(session.get("InputTokens", 0))
    out   = format_k(session.get("OutputTokens", 0))
    cr    = format_k(session.get("CacheR", 0))
    cw    = format_k(session.get("CacheW", 0))
    tokens_line = (
        f"  [dim]IN[/] [yellow]{inp}[/]"
        f"   [dim]OUT[/] [magenta]{out}[/]"
        f"   [dim]CacheR[/] [cyan]{cr}[/]"
        f"   [dim]CacheW[/] [blue]{cw}[/]"
    )

    footer = Group(
        Text.from_markup(context_line),
        Text.from_markup(tokens_line),
        Text(f"  {model} · {mtime} · {turns} turns", style="dim")
    )

    return Group(
        header,
        task_line,
        columns,
        Rule(style="dim"),
        footer
    )