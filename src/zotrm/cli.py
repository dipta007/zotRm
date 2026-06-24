"""Command-line interface: argument parsing and command dispatch.

Subcommands (push / pull / status / sync) and the global --config / --dry-run
flags mirror the original single-file tool exactly.
"""

from __future__ import annotations

import argparse
import tempfile
from configparser import ConfigParser
from pathlib import Path

from zotrm.config import DEFAULT_CONFIG, TAG_DONE, TAG_SYNCED, load_config, log
from zotrm.remarkable import ensure_remote_folder, rmapi
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


def cmd_push(cfg: ConfigParser, dry_run: bool) -> None:
    zot = connect(cfg)
    rm = cfg["remarkable"]
    base = rm.get("folder", "/Papers")
    mirror = _truthy(rm.get("mirror_subcollections", "true"))
    coll_key = find_collection_key(zot, rm["collection"])

    pushed = 0
    for item, folder in iter_items(zot, coll_key, base, mirror):
        key = item["key"]
        title = item["data"].get("title", key)[:70]
        if TAG_SYNCED in tags_of(item):
            continue

        child = pdf_child(zot, key)
        if not child:
            log(f"  skip (no PDF)   {title}")
            continue
        att_key, filename = child

        if dry_run:
            log(f"  would push      {title}  ->  {folder}/{filename}")
            pushed += 1
            continue

        ensure_remote_folder(folder)

        # Prefer the locally-synced PDF; fall back to the Zotero API.
        local = local_pdf_path(cfg, att_key, filename)
        tmp = None
        if local:
            src = str(local)
        else:
            tmp = Path(tempfile.gettempdir()) / filename
            tmp.write_bytes(zot.file(att_key))
            src = str(tmp)

        res = rmapi("put", src, folder, capture=True)
        if res.returncode != 0:
            log(f"  FAILED upload   {title}\n{res.stderr.strip()}")
        else:
            zot.add_tags(item, TAG_SYNCED)
            log(f"  pushed          {title}  ->  {folder}")
            pushed += 1
        if tmp:
            tmp.unlink(missing_ok=True)

    log(
        f"\npush complete: {pushed} paper(s) "
        f"{'would be ' if dry_run else ''}sent to the reMarkable."
    )


def cmd_pull(cfg: ConfigParser, dry_run: bool) -> None:
    zot = connect(cfg)
    rm = cfg["remarkable"]
    base = rm.get("folder", "/Papers")
    mirror = _truthy(rm.get("mirror_subcollections", "true"))
    out_dir = Path(rm.get("output_dir", str(Path.home() / "zotrm-annotated")))
    reattach = _truthy(rm.get("reattach", "true"))
    out_dir.mkdir(parents=True, exist_ok=True)

    coll_key = find_collection_key(zot, rm["collection"])

    pulled = 0
    for item, folder in iter_items(zot, coll_key, base, mirror):
        key = item["key"]
        title = item["data"].get("title", key)[:70]
        item_tags = tags_of(item)
        if TAG_SYNCED not in item_tags or TAG_DONE in item_tags:
            continue

        child = pdf_child(zot, key)
        if not child:
            continue
        _, filename = child
        stem = Path(filename).stem
        remote = f"{folder.rstrip('/')}/{stem}"
        dest = out_dir / f"{stem} (annotated).pdf"

        if dry_run:
            log(f"  would pull      {title}  ->  {dest}")
            pulled += 1
            continue

        # geta = "get annotated": render scribbles onto the original PDF.
        res = rmapi("geta", remote, str(dest), capture=True)
        if res.returncode != 0 or not dest.exists():
            log(f"  no annotations yet / failed   {title}")
            continue

        if reattach:
            try:
                zot.attachment_simple([str(dest)], key)
            except Exception as e:
                log(f"    (re-attach skipped: {e}; file saved to {dest})")

        zot.add_tags(item, TAG_DONE)
        log(f"  pulled          {title}  ->  {dest}")
        pulled += 1

    log(f"\npull complete: {pulled} annotated paper(s) {'would be ' if dry_run else ''}retrieved.")


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
    sub.add_parser("push", help="send queued papers to the reMarkable")
    sub.add_parser("pull", help="bring annotated papers back into Zotero")
    sub.add_parser("status", help="show the queue / on-device / done lists")
    sub.add_parser("sync", help="pull then push, in one go")

    args = p.parse_args(argv)
    cfg = load_config(args.config)

    if args.command == "push":
        cmd_push(cfg, args.dry_run)
    elif args.command == "pull":
        cmd_pull(cfg, args.dry_run)
    elif args.command == "status":
        cmd_status(cfg, args.dry_run)
    elif args.command == "sync":
        cmd_pull(cfg, args.dry_run)
        cmd_push(cfg, args.dry_run)


if __name__ == "__main__":
    main()
