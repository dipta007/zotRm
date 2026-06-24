"""Interactive setup wizard for the config file (the ``zotrm config`` command).

Uses ``questionary`` for arrow-key menus, masked secret entry, and validation.
It is only ever run interactively, so importing this module (and therefore
questionary) is deferred until a wizard command is actually used.
"""

from __future__ import annotations

import configparser
import shutil
from configparser import ConfigParser
from pathlib import Path
from typing import Any

import questionary

from zotrm.config import die, log
from zotrm.zotero import connect


def _ask(question: Any) -> Any:
    """Run a questionary prompt, aborting cleanly if the user cancels (Ctrl-C)."""
    answer = question.ask()
    if answer is None:
        die("setup cancelled")
    return answer


def _text(message: str, default: str = "", required: bool = False) -> str:
    validate: Any = None
    if required:
        validate = lambda v: True if v.strip() else "This field is required."  # noqa: E731
    return str(_ask(questionary.text(message, default=default, validate=validate))).strip()


def _password(message: str, default: str = "") -> str:
    # questionary.password cannot show a default; offer to keep the existing value.
    if default and _confirm("Keep the existing API key?", default=True):
        return default
    return str(_ask(questionary.password(message))).strip()


def _select(message: str, choices: list[str], default: str) -> str:
    return str(_ask(questionary.select(message, choices=choices, default=default)))


def _confirm(message: str, default: bool) -> bool:
    return bool(_ask(questionary.confirm(message, default=default)))


def _path(message: str, default: str = "") -> str:
    return str(_ask(questionary.path(message, default=default))).strip()


def _existing(path: Path) -> dict[str, str]:
    """Flatten an existing config into a single dict for use as defaults."""
    if not path.exists():
        return {}
    cfg = ConfigParser()
    cfg.read(path)
    values: dict[str, str] = {}
    for section in ("zotero", "remarkable"):
        if section in cfg:
            values.update(cfg[section])
    return values


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes")


def _to_configparser(values: dict[str, dict[str, str]]) -> ConfigParser:
    cfg = ConfigParser()
    for section, kv in values.items():
        cfg[section] = {k: v for k, v in kv.items() if v != ""}
    return cfg


def _verify_zotero(cfg: ConfigParser) -> tuple[bool, str]:
    try:
        zot = connect(cfg)
        count = zot.num_items()
        return True, f"Zotero connection OK ({count} items)"
    except Exception as e:
        return False, f"Zotero check failed: {e}"


def _render(values: dict[str, dict[str, str]]) -> str:
    """Render a self-documenting INI file from the collected values."""
    z = values["zotero"]
    r = values["remarkable"]
    lines = [
        "[zotero]",
        f"library_id   = {z['library_id']}",
        f"api_key      = {z['api_key']}",
        f"library_type = {z['library_type']}",
    ]
    if z.get("storage_dir"):
        lines.append("# Local Zotero storage, to avoid re-downloading PDFs.")
        lines.append(f"storage_dir  = {z['storage_dir']}")
    lines += [
        "",
        "[remarkable]",
        "# The Zotero collection whose items get pushed to the tablet.",
        f"collection            = {r['collection']}",
        "# Folder on the reMarkable where papers land (created if missing).",
        f"folder                = {r['folder']}",
        "# Recreate Zotero sub-collections as nested folders on the tablet?",
        f"mirror_subcollections = {r['mirror_subcollections']}",
        "# Where annotated PDFs are written locally when pulled back.",
        f"output_dir            = {r['output_dir']}",
        "# Re-attach the annotated PDF to the Zotero item?",
        f"reattach              = {r['reattach']}",
        "",
    ]
    return "\n".join(lines)


def run_config_wizard(path: Path) -> bool:
    """Collect settings interactively and write them to ``path``.

    Returns True if a config file was written, False if the user aborted.
    """
    prior = _existing(path)
    log("Let's set up zotrm.\n" if not prior else f"Editing {path}\n")

    home_annotated = str(Path.home() / "Zotero" / "annotated")
    values: dict[str, dict[str, str]] = {
        "zotero": {
            "library_id": _text("Zotero library ID", prior.get("library_id", ""), required=True),
            "api_key": _password("Zotero API key", prior.get("api_key", "")),
            "library_type": _select(
                "Library type", ["user", "group"], prior.get("library_type", "user")
            ),
            "storage_dir": _path(
                "Local Zotero storage dir (optional, Enter to skip)",
                prior.get("storage_dir", ""),
            ),
        },
        "remarkable": {
            "collection": _text("Zotero collection to sync", prior.get("collection", "reMarkable")),
            "folder": _text("reMarkable folder", prior.get("folder", "/Papers")),
            "mirror_subcollections": str(
                _confirm(
                    "Mirror sub-collections as nested folders?",
                    _as_bool(prior.get("mirror_subcollections"), True),
                )
            ).lower(),
            "output_dir": _path(
                "Where to save annotated PDFs", prior.get("output_dir", home_annotated)
            ),
            "reattach": str(
                _confirm(
                    "Re-attach the annotated PDF to the Zotero item?",
                    _as_bool(prior.get("reattach"), True),
                )
            ).lower(),
        },
    }

    log("")
    ok, message = _verify_zotero(_to_configparser(values))
    log(f"  {'✓' if ok else '✗'} {message}")
    if shutil.which("rmapi"):
        log("  ✓ rmapi found on PATH")
    else:
        log("  ✗ rmapi not found — install the ddvk fork: brew install rmapi")

    if not ok and not _confirm("Zotero check failed. Save the config anyway?", default=True):
        log("Aborted; nothing written.")
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render(values))
    log(f"  ✓ Wrote {path}")
    return True


def show_config(path: Path) -> None:
    """Print the config location and its values, masking the API key."""
    if not path.exists():
        log(f"No config at {path}. Run 'zotrm config' to create one.")
        return
    cfg = configparser.ConfigParser()
    cfg.read(path)
    log(f"Config: {path}\n")
    for section in cfg.sections():
        log(f"[{section}]")
        for key, value in cfg[section].items():
            shown = "********" if key == "api_key" and value else value
            log(f"  {key} = {shown}")
