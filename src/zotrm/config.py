"""Configuration loading, validation, and small shared helpers.

State for the whole tool lives in Zotero tags (see the tag constants below),
so there is no extra database. Configuration is a plain INI file; see the
README for the template.
"""

from __future__ import annotations

import configparser
import sys
from pathlib import Path
from typing import NoReturn

from rich.console import Console
from rich.text import Text

# Tags used to track per-item state, entirely inside Zotero.
TAG_SYNCED = "rm:synced"  # original pushed to the device
TAG_DONE = "rm:annotated"  # an annotated copy has been pulled back

# Suffix on the single annotated copy zotrm maintains in Zotero, e.g.
# "Paper (annotated).pdf". Used both when creating it and when telling it apart
# from the original on later syncs.
ANNOTATED_SUFFIX = " (annotated)"

DEFAULT_CONFIG = Path.home() / ".config" / "zotrm" / "config.ini"

_STDOUT = Console(soft_wrap=True, highlight=False)
_STDERR = Console(stderr=True, soft_wrap=True, highlight=False)

_BADGE_STYLES: dict[str, tuple[str, str, str]] = {
    "pushed": ("↑ pushed", "bold green", "bold"),
    "refreshed": ("↻ refreshed", "bold cyan", "bold"),
    "moved": ("↪ moved", "bold magenta", ""),
    "removed": ("− removed", "bold yellow", "dim"),
    "saved locally": ("↓ saved locally", "bold yellow", ""),
    "would push": ("• would push", "bold blue", ""),
    "would refresh": ("• would refresh", "bold blue", ""),
    "no annotations yet": ("· no annotations yet", "dim", "dim"),
    "skip (no PDF)": ("! skip (no PDF)", "yellow", "dim"),
    "FAILED upload": ("✗ FAILED upload", "bold red", "red"),
}

_LINE_STYLES: tuple[tuple[str, str], ...] = (
    ("\nsync complete", "bold green"),
    ("\nQueued", "bold yellow"),
    ("\nOn reMarkable", "bold cyan"),
    ("\nAnnotated", "bold green"),
    ("Collection:", "bold"),
    ("Config:", "bold"),
    ("[", "bold cyan"),
    ("  ✓", "bold green"),
    ("  ✗", "bold red"),
    ("    (re-attach failed:", "yellow"),
)


def _format_log(msg: str) -> Text:
    """Format a log line with Rich styles while preserving plain-text structure."""
    match = next((k for k in _BADGE_STYLES if msg.startswith(f"  {k}   ")), None)
    if match:
        badge, badge_style, body_style = _BADGE_STYLES[match]
        body = msg[len(f"  {match}") :].lstrip(" ")
        head, *tail = body.split("  ->  ", 1)
        t = Text(f"  {badge:<20}  ", style=badge_style)
        t.append(head, style=body_style)
        for target in tail:
            t.append("  →  ", style="dim")
            t.append(target, style="cyan")
        return t
    if msg.startswith("  - "):
        title, _, folder = msg.rpartition("   ")
        t = Text(title)
        t.append(f"   {folder}", style="dim cyan")
        return t
    style = next((s for prefix, s in _LINE_STYLES if msg.startswith(prefix)), "")
    return Text(msg, style=style)


def die(msg: str, code: int = 1) -> NoReturn:
    """Print an error to stderr and exit with a non-zero status."""
    t = Text("✗ error: ", style="bold red")
    t.append(msg, style="red")
    _STDERR.print(t)
    sys.exit(code)


def log(msg: str) -> None:
    """Print a line of progress output, flushing so cron logs stay live."""
    _STDOUT.print(_format_log(msg))
    sys.stdout.flush()


def load_config(path: Path) -> configparser.ConfigParser:
    """Load and minimally validate the INI config, or exit with an error."""
    if not path.exists():
        die(f"config not found at {path}\n       create it (see the README for a template).")
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(path)
    for section in ("zotero", "remarkable"):
        if section not in cfg:
            die(f"[{section}] section missing from {path}")
    return cfg
