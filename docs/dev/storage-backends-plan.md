# Plan: re-attach for Zotero storage **and** WebDAV

## Problem

`pull` renders the annotated PDF and re-attaches it to the Zotero item via pyzotero's
`attachment_simple`, which uploads through the **Zotero Web API**. The Web API only stores
files in **Zotero's own file storage** (quota-limited). It has **no concept of WebDAV** —
WebDAV is a desktop-client feature. So for WebDAV users every re-attach fails with HTTP 413
(quota), and today that also:

- leaves an **orphaned attachment** (the item is created before the file upload fails), and
- still tags the paper `rm:annotated`, so it never retries, and
- names the file from the full path, not the basename.

## Goal

One re-attach path that works for both storage types, selected by config, with clean
error handling and no duplicate annotated copies.

## Background: how Zotero stores attachment files

| Mode | File lives in | Set up in | API can upload? |
| --- | --- | --- | --- |
| Zotero storage | Zotero servers (quota) | account (free/sub) | yes (Web API) |
| WebDAV | your server, as `<KEY>.zip` + `<KEY>.prop` | desktop client | no — client only |

For WebDAV, each attachment `KEY` is stored as two files in a `zotero/` folder on the
server:

- `KEY.zip` — the attachment file, zipped.
- `KEY.prop` — `<properties version="1"><mtime>…</mtime><hash>MD5</hash></properties>`.

The **item metadata** still syncs through the Web API in both modes; only the **file
bytes** differ.

## Configuration (new)

```ini
[zotero]
…
# How your Zotero attachment files are stored: zotero | webdav | none
file_mode    = webdav
# Only for file_mode = webdav:
webdav_url   = https://cloud.example.com/remote.php/dav/files/me/zotero
webdav_user  = me
webdav_pass  = app-specific-password
```

- `file_mode = zotero` — current behaviour (Web API upload), but with the error-handling
  fixes below.
- `file_mode = webdav` — upload to the server directly (details below).
- `file_mode = none` — never re-attach; just keep the local copy in `output_dir`
  (equivalent to today's `reattach = false`).
- `reattach = true|false` stays as the master on/off; `file_mode` chooses the backend.
- The wizard (`zotrm config`) gains a "How are your Zotero files stored?" question and,
  for WebDAV, prompts for url/user/password. `config --show` masks the password.

## Architecture

A small backend abstraction (new `src/zotrm/storage.py`):

```python
def reattach(zot, cfg, parent_key: str, local_pdf: Path, filename: str) -> None
```

It (1) removes any existing annotated copy on the parent (replace, not duplicate),
(2) dispatches to the chosen backend, (3) rolls back + raises a typed error on failure.

- **ZoteroBackend** — `attachment_both`/upload via the Web API. Map 413 → `QuotaError`
  with an actionable message (suggest WebDAV or `file_mode = none`).
- **WebDavBackend**:
  1. Create the `imported_file` attachment item via the API (metadata only, quota-free) →
     get `KEY`.
  2. Compute the file's MD5 and mtime.
  3. Build `KEY.zip` (the PDF, with a clean basename inside) and `KEY.prop`.
  4. `PUT` both to `<webdav_url>/KEY.zip` and `<webdav_url>/KEY.prop` (HTTP basic auth).
  5. Register the file on the API item (set `md5` + `mtime`) so other clients verify and
     download it.
- **NoneBackend** — no-op; the local copy in `output_dir` is the deliverable.

Dependency: WebDAV is plain HTTP `PUT` — use `urllib`/`http.client` from stdlib (no new
dependency), or `httpx` if it's already pulled in transitively. Prefer stdlib.

## Error-handling fixes (apply regardless of backend)

- Wrap re-attach. **On failure: do not tag `rm:annotated`** (so the next pull retries) and
  **delete any attachment item we created** (no orphan). Always keep the local copy and
  print a clear, actionable message.
- Use the **basename** for the attachment filename, never the full path.

## Replace-single-copy (ties into the earlier sync redesign)

Before attaching, find an existing `… (annotated).pdf` child on the parent and delete it
(and its storage/WebDAV file) so re-pulling refreshes one copy instead of accumulating.

## Testing

- Unit: mock the API + WebDAV `PUT`s; assert correct `KEY.zip`/`KEY.prop`, basename
  filename, rollback-on-failure, no false `rm:annotated`, single-copy replace.
- Integration: against a **real WebDAV server** (the maintainer has one) on a throwaway
  collection; verify another Zotero client downloads the file after sync.
- Keep 100% coverage on `src` with mocks.

## Open questions / unknowns to confirm

1. **WebDAV URL convention** — does Zotero point at the parent dir and create `zotero/`
   itself, or at the `zotero/` dir directly? (Nextcloud vs. generic WebDAV differ.) Confirm
   against the real server.
2. **File registration** — exact API call/fields (`md5`, `mtime`) needed after a WebDAV
   upload so other clients don't re-download or flag a conflict.
3. **`.prop` version field** and any hash format specifics for current Zotero.
4. **Auto-detect?** Could infer `webdav` when `webdav_url` is set; otherwise default
   `zotero`. Keep it explicit in the wizard to avoid surprises.

## Rollout

1. Ship the **error-handling fixes** first (no orphan, no false done-tag, basename) — they
   help everyone immediately and are backend-agnostic. (Could be `0.1.2`.)
2. Then the **storage backend abstraction + WebDAV**, validated on the real server. (`0.2.0`,
   alongside the keep-original / single-annotated-copy sync redesign.)

## Security note

`webdav_pass` sits in a plaintext config file. Recommend an **app-specific password**, and
have `config --show` mask it. Document this clearly.
