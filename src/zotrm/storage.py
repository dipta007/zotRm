"""Re-attach the annotated PDF to a Zotero item, via the configured file backend.

``file_mode`` selects where the file bytes go:

- ``zotero`` — upload through the Zotero Web API (counts against Zotero storage).
- ``webdav`` — upload ``<KEY>.zip`` + ``<KEY>.prop`` to the user's WebDAV server
  (``{webdav_url}/zotero/``), the same layout the Zotero desktop client uses.
- ``none``   — don't re-attach; the local copy in ``output_dir`` is the deliverable.

In every mode the single annotated copy is *replaced*, never duplicated, and a
failure rolls back so the caller can avoid marking the item done.
"""

from __future__ import annotations

import base64
import hashlib
import io
import os
import urllib.request
import zipfile
from configparser import ConfigParser
from pathlib import Path
from typing import Any

from zotrm.config import log
from zotrm.zotero import annotated_child


def file_mode(cfg: ConfigParser) -> str:
    """Resolve the effective file backend: ``zotero`` | ``webdav`` | ``none``."""
    z = cfg["zotero"]
    mode = z.get("file_mode", "").strip().lower()
    if mode in ("zotero", "webdav", "none"):
        return mode
    # Back-compat: the old `reattach = false` means "don't re-attach".
    reattach = cfg["remarkable"].get("reattach", "true").strip().lower()
    if reattach in ("0", "false", "no"):
        return "none"
    return "zotero"


def reattach(zot: Any, cfg: ConfigParser, parent_key: str, local_pdf: Path) -> bool:
    """Replace the parent's single annotated copy with ``local_pdf``.

    Returns True if attached (or intentionally skipped in ``none`` mode), False if
    a backend failed — in which case the item should not be marked done.
    """
    mode = file_mode(cfg)
    if mode == "none":
        return True

    filename = local_pdf.name
    try:
        existing = annotated_child(zot, parent_key, filename)
        if existing is not None:
            zot.delete_item(existing)
        if mode == "webdav":
            _attach_webdav(zot, cfg, parent_key, local_pdf, filename)
        else:
            _attach_zotero(zot, parent_key, local_pdf, filename)
        return True
    except Exception as e:  # noqa: BLE001 - any backend error: keep the local copy, retry later
        log(f"    (re-attach failed: {e}; file saved to {local_pdf})")
        return False


def _attach_zotero(zot: Any, parent_key: str, local_pdf: Path, filename: str) -> None:
    """Upload via the Zotero Web API, keeping a clean basename filename.

    pyzotero stores the path it is given as the filename, so call it from inside
    the file's directory with just the basename.
    """
    cwd = os.getcwd()
    try:
        os.chdir(local_pdf.parent)
        zot.attachment_simple([filename], parent_key)
    finally:
        os.chdir(cwd)


def _attach_webdav(
    zot: Any, cfg: ConfigParser, parent_key: str, local_pdf: Path, filename: str
) -> None:
    """Create the attachment item, then upload <KEY>.zip + <KEY>.prop to WebDAV."""
    z = cfg["zotero"]
    base = z["webdav_url"].rstrip("/")
    user = z.get("webdav_user", "")
    password = z.get("webdav_pass", "")

    data = local_pdf.read_bytes()
    md5 = hashlib.md5(data).hexdigest()  # noqa: S324 - Zotero requires md5, not for security
    mtime = int(local_pdf.stat().st_mtime * 1000)

    key = _create_attachment(zot, parent_key, filename, md5, mtime)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(filename, data)
    prop = f'<properties version="1"><mtime>{mtime}</mtime><hash>{md5}</hash></properties>'

    _webdav_put(f"{base}/zotero/{key}.zip", buf.getvalue(), user, password)
    _webdav_put(f"{base}/zotero/{key}.prop", prop.encode(), user, password)


def _create_attachment(zot: Any, parent_key: str, filename: str, md5: str, mtime: int) -> str:
    """Create an imported_file attachment item (metadata only) and return its key."""
    template = zot.item_template("attachment", "imported_file")
    template["title"] = filename
    template["filename"] = filename
    template["contentType"] = "application/pdf"
    template["parentItem"] = parent_key
    template["md5"] = md5
    template["mtime"] = mtime
    resp = zot.create_items([template])
    return str(resp["success"]["0"])


def _webdav_put(url: str, body: bytes, user: str, password: str) -> None:
    req = urllib.request.Request(url, data=body, method="PUT")  # noqa: S310 - user-configured URL
    if user:
        token = base64.b64encode(f"{user}:{password}".encode()).decode()
        req.add_header("Authorization", f"Basic {token}")
    with urllib.request.urlopen(req) as resp:  # noqa: S310
        if resp.status not in (200, 201, 204):
            raise RuntimeError(f"WebDAV PUT {url} -> HTTP {resp.status}")
