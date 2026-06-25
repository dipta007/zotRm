"""pyzotero wrapper: connection, collection walk, and tag helpers.

``pyzotero`` ships no type stubs, so the live Zotero client is typed as
``Any``; the helpers below pin down the small slices of its API we use.
"""

from __future__ import annotations

from collections.abc import Iterator
from configparser import ConfigParser
from pathlib import Path
from typing import Any

from zotrm.config import ANNOTATED_SUFFIX, die


def connect(cfg: ConfigParser) -> Any:
    """Build a pyzotero client from the [zotero] config section."""
    from pyzotero import zotero  # imported lazily so --help works without it

    z = cfg["zotero"]
    return zotero.Zotero(
        z["library_id"],
        z.get("library_type", "user"),
        z["api_key"],
    )


def find_collection_key(zot: Any, name: str) -> str:
    """Return the key of the collection named ``name``, or exit if missing."""
    for c in zot.everything(zot.collections()):
        if c["data"]["name"] == name:
            return str(c["key"])
    die(f"no Zotero collection named {name!r} found")


def _is_annotated(filename: str) -> bool:
    return filename.endswith(f"{ANNOTATED_SUFFIX}.pdf")


def pdf_child(zot: Any, item_key: str) -> tuple[str, str] | None:
    """Return (attachment_key, filename) of the first *original* PDF attachment.

    Skips the annotated copy zotrm maintains, so push always sends the original.
    """
    for child in zot.children(item_key):
        data = child["data"]
        filename = data.get("filename")
        if (
            data.get("contentType") == "application/pdf"
            and filename
            and not _is_annotated(filename)
        ):
            return str(child["key"]), str(filename)
    return None


def annotated_child(zot: Any, item_key: str, filename: str) -> Any | None:
    """Return the existing attachment item whose filename is ``filename``, or None.

    Used to replace (not duplicate) the single annotated copy on re-sync.
    """
    for child in zot.children(item_key):
        if child["data"].get("filename") == filename:
            return child
    return None


def local_pdf_path(cfg: ConfigParser, att_key: str, filename: str) -> Path | None:
    """Return the locally-synced PDF path if it exists, else None."""
    storage = cfg["zotero"].get("storage_dir", "").strip()
    if storage:
        p = Path(storage) / att_key / filename
        if p.exists():
            return p
    return None


def tags_of(item: Any) -> set[str]:
    """Return the set of tag strings on a Zotero item."""
    return {t["tag"] for t in item["data"].get("tags", [])}


def iter_items(
    zot: Any, coll_key: str, base_folder: str, mirror: bool
) -> Iterator[tuple[Any, str]]:
    """Yield (item, remote_folder) for every item under a collection.

    If mirror is True, Zotero sub-collections are recreated as nested
    reMarkable folders (e.g. reMarkable/Multimodal/Retrieval). If False,
    everything lands flat in base_folder.
    """
    for item in zot.everything(zot.collection_items_top(coll_key)):
        yield item, base_folder
    if not mirror:
        return
    for sub in zot.everything(zot.collections_sub(coll_key)):
        sub_folder = f"{base_folder.rstrip('/')}/{sub['data']['name']}"
        yield from iter_items(zot, sub["key"], sub_folder, mirror)
