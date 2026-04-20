import time
from rich.console import Group
from rich.text import Text
from rich.rule import Rule


def render_extended_session(session):
    """Compact extended view — no nested Panel borders, max ~8 lines."""
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
    path  = session.get("ProjectPath", "?")[:40]
    ai    = session.get("AI", "?")
    line1 = Text.assemble(
        ("  SESSION ", "bold bright_white"),
        (f"▶{sid}", "bold cyan"),
        ("  ·  ", "dim"),
        (path, "italic white"),
        ("   ", ""),
        (f"[{ai}] ", "bold yellow"),
        status_label,
    )

    # Line 2 — task summary
    summary = session.get("Summary", "No task active")[:80]
    line2 = f"  [dim]task[/] [white]{summary}[/]"

    # Line 3 — token row
    inp   = format_k(session.get("InputTokens", 0))
    out   = format_k(session.get("OutputTokens", 0))
    cr    = format_k(session.get("CacheR", 0))
    cw    = format_k(session.get("CacheW", 0))
    line3 = (
        f"  [dim]IN[/] [yellow]{inp}[/]"
        f"   [dim]OUT[/] [magenta]{out}[/]"
        f"   [dim]CacheR[/] [cyan]{cr}[/]"
        f"   [dim]CacheW[/] [blue]{cw}[/]"
    )

    # Line 4 — context bar
    ctx_pct = 0.0
    if session.get("ContextWindow", 0) > 0:
        ctx_pct = (session.get("LastContext", 0) / session["ContextWindow"]) * 100
    color  = "green" if ctx_pct < 60 else ("yellow" if ctx_pct < 85 else "red")
    filled = int((ctx_pct / 100) * 24)
    bar    = f"[{color}]{'█' * filled}[/][dim]{'░' * (24 - filled)}[/]"
    line4  = f"  [dim]Context[/] {bar} [bold]{ctx_pct:.1f}%[/]"

    # Line 5 — footer
    mtime = time.strftime("%H:%M:%S", time.localtime(session.get("mtime", 0)))
    model = session.get("Model", "-")[:15]
    turns = str(session.get("TurnCount", "-"))
    line5 = (
        f"  [dim]Model[/] [white]{model}[/]"
        f"   [dim]Turns[/] [white]{turns}[/]"
        f"   [dim]MTime[/] [white]{mtime}[/]"
    )

    return Group(
        Rule(title="[bold blue] Session Details [/]", style="blue"),
        line1,
        line2,
        Rule(style="dim"),
        line3,
        line4,
        line5,
    )
