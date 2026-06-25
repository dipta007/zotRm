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

# Tags used to track per-item state, entirely inside Zotero.
TAG_SYNCED = "rm:synced"  # original pushed to the device
TAG_DONE = "rm:annotated"  # an annotated copy has been pulled back

# Suffix on the single annotated copy zotrm maintains in Zotero, e.g.
# "Paper (annotated).pdf". Used both when creating it and when telling it apart
# from the original on later syncs.
ANNOTATED_SUFFIX = " (annotated)"

DEFAULT_CONFIG = Path.home() / ".config" / "zotrm" / "config.ini"


def die(msg: str, code: int = 1) -> NoReturn:
    """Print an error to stderr and exit with a non-zero status."""
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def log(msg: str) -> None:
    """Print a line of progress output, flushing so cron logs stay live."""
    print(msg, flush=True)


def load_config(path: Path) -> configparser.ConfigParser:
    """Load and minimally validate the INI config, or exit with an error."""
    if not path.exists():
        die(f"config not found at {path}\n       create it (see the README for a template).")
    cfg = configparser.ConfigParser()
    cfg.read(path)
    for section in ("zotero", "remarkable"):
        if section not in cfg:
            die(f"[{section}] section missing from {path}")
    return cfg
