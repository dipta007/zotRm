"""Command-line interface: argument parsing and command dispatch.

The workflow is a single ``sync`` command: it pushes the original PDF the first
time it sees a paper, and on later runs refreshes one annotated copy from the
tablet (the original is never touched again). ``status`` shows the state.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from configparser import ConfigParser
from pathlib import Path
from typing import Any

from zotrm.config import (
    ANNOTATED_SUFFIX,
    DEFAULT_CONFIG,
    TAG_DONE,
    TAG_SYNCED,
    load_config,
    log,
)
from zotrm.remarkable import ensure_remote_folder, rmapi
from zotrm.storage import reattach
from zotrm.zotero import (
    connect,
    find_collection_key,
    iter_items,
    local_pdf_path,
    pdf_child,
    tags_of,
)


def _truthy(value: str) -> bool:
    return value.lower() in ("1", "true", "yes")


def _interactive() -> bool:
    """True when we have a real terminal (so it's safe to prompt)."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def _source_pdf(
    cfg: ConfigParser, zot: Any, att_key: str, filename: str
) -> tuple[str, Path | None]:
    """Return (path, temp_to_clean): the local PDF, or a temp download from the API."""
    local = local_pdf_path(cfg, att_key, filename)
    if local:
        return str(local), None
    tmp = Path(tempfile.gettempdir()) / filename
    tmp.write_bytes(zot.file(att_key))
    return str(tmp), tmp


def cmd_sync(cfg: ConfigParser, dry_run: bool) -> None:
    zot = connect(cfg)
    rm = cfg["remarkable"]
    base = rm.get("folder", "/Papers")
    mirror = _truthy(rm.get("mirror_subcollections", "true"))
    out_dir = Path(rm.get("output_dir", str(Path.home() / "zotrm-annotated")))
    out_dir.mkdir(parents=True, exist_ok=True)
    coll_key = find_collection_key(zot, rm["collection"])

    pushed = 0
    refreshed = 0
    for item, folder in iter_items(zot, coll_key, base, mirror):
        key = item["key"]
        title = item["data"].get("title", key)[:70]
        tags = tags_of(item)

        child = pdf_child(zot, key)
        if not child:
            log(f"  skip (no PDF)   {title}")
            continue
        att_key, filename = child

        if TAG_SYNCED not in tags:
            # First time: push the original PDF to the tablet.
            if dry_run:
                log(f"  would push      {title}  ->  {folder}/{filename}")
                pushed += 1
                continue
            ensure_remote_folder(folder)
            src, tmp = _source_pdf(cfg, zot, att_key, filename)
            res = rmapi("put", src, folder, capture=True)
            if tmp:
                tmp.unlink(missing_ok=True)
            if res.returncode != 0:
                log(f"  FAILED upload   {title}\n{res.stderr.strip()}")
                continue
            zot.add_tags(item, TAG_SYNCED)
            log(f"  pushed          {title}  ->  {folder}")
            pushed += 1
            continue

        # Already on the tablet: refresh the single annotated copy.
        stem = Path(filename).stem
        remote = f"{folder.rstrip('/')}/{stem}"
        dest = out_dir / f"{stem}{ANNOTATED_SUFFIX}.pdf"
        if dry_run:
            log(f"  would refresh   {title}  ->  {dest}")
            refreshed += 1
            continue

        # geta writes "<name>-annotations.pdf" into its working dir and ignores
        # any output path, so run it in a temp dir and collect the result.
        with tempfile.TemporaryDirectory() as tmpdir:
            res = rmapi("geta", "--a", remote, capture=True, cwd=tmpdir)
            produced = next(Path(tmpdir).glob("*-annotations.pdf"), None)
            if res.returncode != 0 or produced is None:
                log(f"  no annotations yet   {title}")
                continue
            shutil.move(str(produced), str(dest))

        if reattach(zot, cfg, key, dest):
            if TAG_DONE not in tags:
                zot.add_tags(item, TAG_DONE)
            log(f"  refreshed       {title}  ->  {dest}")
        else:
            log(f"  saved locally   {title}  ->  {dest}")
        refreshed += 1

    suffix = " (dry run)" if dry_run else ""
    log(f"\nsync complete{suffix}: {pushed} pushed, {refreshed} refreshed.")


def cmd_status(cfg: ConfigParser, dry_run: bool) -> None:
    zot = connect(cfg)
    rm = cfg["remarkable"]
    base = rm.get("folder", "/Papers")
    mirror = _truthy(rm.get("mirror_subcollections", "true"))
    coll_key = find_collection_key(zot, rm["collection"])

    queued: list[str] = []
    on_device: list[str] = []
    done: list[str] = []
    for item, folder in iter_items(zot, coll_key, base, mirror):
        t = tags_of(item)
        title = item["data"].get("title", item["key"])[:60]
        row = f"{title}   [{folder}]"
        if TAG_DONE in t:
            done.append(row)
        elif TAG_SYNCED in t:
            on_device.append(row)
        else:
            queued.append(row)

    def block(name: str, rows: list[str]) -> None:
        log(f"\n{name} ({len(rows)})")
        for r in rows:
            log(f"  - {r}")

    log(f"Collection: {rm['collection']}  (mirror={mirror})")
    block("Queued (will push)", queued)
    block("On reMarkable (reading)", on_device)
    block("Annotated (back in Zotero)", done)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        prog="zotrm",
        description="Bridge a Zotero collection to a reMarkable Paper Pro and back.",
    )
    p.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"config file (default: {DEFAULT_CONFIG})",
    )
    p.add_argument("--dry-run", action="store_true", help="show what would happen, change nothing")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("sync", help="push new papers and refresh annotations (the whole workflow)")
    sub.add_parser("status", help="show the queue / on-device / annotated lists")
    config_p = sub.add_parser("config", help="create or edit your configuration")
    config_p.add_argument(
        "--show", action="store_true", help="print the current config location and values"
    )
    cron_p = sub.add_parser("cron", help="schedule an automatic sync")
    cron_p.add_argument("--remove", action="store_true", help="remove the scheduled sync")
    cron_p.add_argument("--show", action="store_true", help="show the scheduled sync, if any")

    args = p.parse_args(argv)

    if args.command == "config":
        from zotrm.wizard import run_config_wizard, show_config

        if args.show:
            show_config(args.config)
        else:
            run_config_wizard(args.config)
        return

    if args.command == "cron":
        from zotrm.cron import remove_cron_job, run_cron_setup, show_cron_job

        if args.remove:
            log("Removed the scheduled sync." if remove_cron_job() else "No scheduled sync found.")
        elif args.show:
            line = show_cron_job()
            log(line if line else "No scheduled sync found.")
        else:
            run_cron_setup(args.config)
        return

    # sync / status need a config. On first run, if we have a terminal, launch
    # the wizard; otherwise fall through to a clean error.
    if not args.config.exists() and _interactive():
        log("No config found yet — let's set it up first.\n")
        from zotrm.wizard import run_config_wizard

        if not run_config_wizard(args.config):
            return
        log("")

    cfg = load_config(args.config)

    if args.command == "status":
        cmd_status(cfg, args.dry_run)
    else:  # sync
        cmd_sync(cfg, args.dry_run)


if __name__ == "__main__":
    main()
