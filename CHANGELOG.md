# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.8] - 2026-10-28

### Fixed

- Log `✓ up to date` and skip `reattach` / `refreshed` counting when an already-annotated
  paper's rendered PDF bytes have not changed since the last sync.

## [0.2.7] - 2026-10-28

### Added

- Styled CLI output with `rich`: color-coded action badges (`↑ pushed`, `↻ refreshed`,
  `↪ moved`, `− removed`, dimmed `· no annotations yet`), styled arrows and folder paths,
  and highlighted `zotrm status` sections.

## [0.2.6] - 2026-10-28

### Fixed

- Batch new tags (`rm:synced:<key>` and `rm:annotated`) into a single `zot.add_tags` call
  per item so Zotero does not reject a second `PATCH` with HTTP 412 (`Precondition Failed`).

## [0.2.5] - 2026-10-28

### Fixed

- Scope remote filename disambiguation per-folder `(folder, stem)` so the same paper in two
  different sub-collections is not falsely renamed or marked for removal.
- Retry `rmapi` commands with backoff (`2s`, `5s`, `10s`) when reMarkable's auth endpoint
  returns HTTP 429 (`status 429`).
- Verify `rmapi rm`, `rmapi mv`, and `rmapi mkdir` exit codes before logging `removed` /
  `moved` or caching created folders.

## [0.2.4] - 2026-10-28

### Changed

- Include the count of removed papers (`X pushed, Y refreshed, Z removed.`) in the
  `sync complete` summary line.

## [0.2.3] - 2026-10-28

### Added

- Move already-synced tablet papers (`rmapi mv`) when they are moved between Zotero
  sub-collections, and prune (`rmapi rm`) tablet papers that have been removed from the
  Zotero collection (`prune = true` by default).

## [0.2.2] - 2026-10-28

### Fixed

- Refresh `rmapi`'s local tree cache (`rmapi refresh`), recreate the remote folder hierarchy,
  and retry `rmapi put` once when an upload fails with `directory doesn't exist` after a
  folder was renamed or deleted on the tablet.

## [0.2.1] - 2026-10-28

### Fixed

- Check local `~/Zotero/storage` by default when `storage_dir` is not explicitly set in
  `config.ini`, and fall back to downloading `<KEY>.zip` from WebDAV when `file_mode = webdav`
  instead of failing with HTTP 404 against Zotero's cloud storage.

## [0.2.0] - 2026-10-27

### Changed

- Collapsed the workflow into a single `zotrm sync` command (removed `push` and `pull`).
  The first sync pushes the original PDF; later syncs refresh **one** always-current
  `… (annotated).pdf` in Zotero — the original is never touched and nothing is duplicated.

### Added

- **reMarkable Paper Pro (v6) annotation support.** `rmapi`'s renderer can't read the
  Paper Pro's v6 `.rm` format, so `sync` now downloads the raw bundle (`rmapi get`) and
  rebuilds annotations itself (`rmscene` + `pypdf`): text highlights (including multi-line
  highlights) become editable PDF `/Highlight` annotations (Zotero imports them as native
  highlights, carrying the text), and pen strokes become `/Ink` with an appearance stream
  (skipping eraser strokes). New deps: `rmscene`, `pypdf`.
- `file_mode` setting (`zotero` | `webdav` | `none`) selecting where the annotated copy is
  stored, including a **WebDAV backend** that uploads `<KEY>.zip` + `<KEY>.prop` to
  `{webdav_url}/zotero/`. The wizard collects WebDAV URL + credentials.

### Fixed

- Re-attach failures no longer delete the previous annotated attachment, leave an orphaned
  attachment, or wrongly mark a paper done, and the annotated copy keeps a clean basename
  filename.
- Unchanged annotated PDFs (matching MD5) skip redundant Zotero/WebDAV delete and
  re-upload on subsequent syncs.
- Duplicate PDF filenames in a collection are deterministically disambiguated with
  `(<item_key>)`.
- `ConfigParser` interpolation is disabled so `%` in passwords or WebDAV URLs works;
  `config.ini` is written with `0600` permissions; `~` and relative paths are expanded for
  `storage_dir`, `output_dir`, and `--config`; cron paths are shell-quoted and `rmapi`
  searches common Homebrew/user binary paths under cron.

## [0.1.1] - 2026-06-24

### Fixed

- `pull` now works with current `rmapi` (ddvk v0.0.34+). It runs `geta --a` in a temp
  directory and collects the `<name>-annotations.pdf` that rmapi writes there, instead of
  passing an output path that newer rmapi silently ignores. Previously every pull reported
  "no annotations yet / failed" even when annotations existed.

## [0.1.0] - 2026-06-23

### Added

- `push`, `pull`, `status`, and `sync` commands to move PDFs between a Zotero collection
  and a reMarkable Paper Pro, tracking state with Zotero tags (`rm:synced`,
  `rm:annotated`).
- Sub-collection mirroring: Zotero sub-collections become nested folders on the tablet.
- `zotrm config` — interactive setup wizard with a live Zotero check and an `rmapi`
  presence check; runs automatically on first use.
- `zotrm cron` — schedule an automatic sync (with `--remove` / `--show`).
- `--config` and `--dry-run` global flags.
- Full type hints (`mypy --strict`), `ruff` lint/format, and a test suite at 100%
  coverage.

[Unreleased]: https://github.com/dipta007/zotRm/compare/v0.2.8...HEAD
[0.2.8]: https://github.com/dipta007/zotRm/compare/v0.2.7...v0.2.8
[0.2.7]: https://github.com/dipta007/zotRm/compare/v0.2.6...v0.2.7
[0.2.6]: https://github.com/dipta007/zotRm/compare/v0.2.5...v0.2.6
[0.2.5]: https://github.com/dipta007/zotRm/compare/v0.2.4...v0.2.5
[0.2.4]: https://github.com/dipta007/zotRm/compare/v0.2.3...v0.2.4
[0.2.3]: https://github.com/dipta007/zotRm/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/dipta007/zotRm/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/dipta007/zotRm/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/dipta007/zotRm/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/dipta007/zotRm/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/dipta007/zotRm/releases/tag/v0.1.0
