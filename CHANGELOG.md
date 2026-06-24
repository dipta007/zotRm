# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/dipta007/zotRm/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/dipta007/zotRm/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/dipta007/zotRm/releases/tag/v0.1.0
