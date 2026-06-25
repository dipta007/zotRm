# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

`zotrm` bridges a Zotero collection and a reMarkable Paper Pro. See `README.md` for the
user-facing workflow and `docs/advanced-usage.md` for the full config reference.

## Commands

Everything goes through `uv` (never pip/poetry).

```sh
uv sync                       # install deps + dev group, create .venv
uv run pytest                 # full suite — ENFORCES 100% coverage (fails below)
uv run pytest tests/test_sync.py::test_sync_first_run_pushes_original   # single test
uv run pytest -k webdav        # by keyword
uv run ruff check .            # lint
uv run ruff format .           # format (line length 100)
uv run mypy src                # type-check, strict
uv build                       # wheel + sdist into dist/
uv tool install . --force --reinstall   # put the current source on PATH as `zotrm`
```

The four gates that CI (`.github/workflows/ci.yml`, Python 3.11–3.13) and the release
workflow both run: `ruff check .`, `ruff format --check .`, `mypy src`, `uv run pytest`.
Coverage is enforced via `--cov-fail-under=100` in `pyproject.toml`; new code needs tests
(branch coverage on). The only coverage exclusions are `if __name__ == "__main__":` guards.

## Architecture

A `src/` layout package (`src/zotrm/`). The whole workflow is **one command, `zotrm sync`**,
driven entirely by two Zotero tags — there is no database:

- `rm:synced` — the original PDF has been pushed to the tablet.
- `rm:annotated` — an annotated copy has been pulled back at least once.

`sync` logic per item (`cli.py:cmd_sync`): **first time** (`rm:synced` absent) push the
*original* PDF to the tablet; **after that** run `rmapi geta` and refresh a single
`… (annotated).pdf` in Zotero. The original is never re-pushed and never modified; the
annotated copy is replaced (not duplicated) each run. `geta` failing means "no annotations
yet" and the item is left to retry. `cron` schedules `zotrm sync`.

Module responsibilities (each is small and single-purpose):

- `cli.py` — argparse, dispatch, and the `cmd_sync` / `cmd_status` logic. `wizard`/`cron`
  are imported lazily inside `main()` so core runs don't pull in `questionary`.
- `config.py` — INI load/validate (stdlib `configparser`, **not** TOML), shared `die`/`log`,
  and the `TAG_*` / `ANNOTATED_SUFFIX` constants.
- `zotero.py` — pyzotero wrapper. `connect` imports pyzotero lazily. `pdf_child` returns the
  *original* PDF (skips anything ending in the annotated suffix); `annotated_child` finds the
  existing annotated copy for replacement. `iter_items` walks sub-collections for folder
  mirroring.
- `remarkable.py` — thin `rmapi` subprocess wrapper (+ remote-folder creation), with a clean
  "rmapi not found" exit.
- `storage.py` — the re-attach backends, selected by `file_mode` (`zotero` | `webdav` |
  `none`). `reattach()` removes the old annotated copy then dispatches; a backend failure
  returns `False` so the caller does **not** tag the item done (no orphan, retry next sync).
- `wizard.py` (`zotrm config`) — questionary-driven setup; collects `file_mode` + WebDAV
  settings, verifies the Zotero key live, writes a self-documenting INI.
- `cron.py` (`zotrm cron`) — builds a schedule and edits the user crontab idempotently
  (tagged `# zotrm-sync`).

### External dependency: rmapi (the ddvk fork)

`rmapi` is a **runtime system prerequisite**, not a Python dep — never `uv add` it. Its CLI
is quirky and bit us: `geta` **ignores any output-path argument** and writes
`<name>-annotations.pdf` into its *working directory*, and needs `--a` for the full document.
So `cmd_sync` runs `rmapi("geta", "--a", remote, cwd=tmpdir)` and collects `*-annotations.pdf`
from that temp dir. The remote doc name is the original PDF's filename stem.

### WebDAV backend (`storage._attach_webdav`)

The Zotero **Web API only uploads to Zotero's own (quota-limited) storage** — it has no
WebDAV. For WebDAV users, `zotrm` itself uploads `<KEY>.zip` + `<KEY>.prop` (stdlib `urllib`
HTTP PUT) to `{webdav_url}/zotero/`, the layout the Zotero desktop client uses. This path is
unit-tested with mocked PUTs but the live `.prop`/registration behavior is **unverified
against a real server** — validate end-to-end before trusting changes here.

## Testing conventions

All external systems are faked, never hit: `tests/conftest.py` provides `FakeZotero` (the
pyzotero surface) and `FakeQuestionary`; tests monkeypatch `zotrm.remarkable.subprocess.run`,
`zotrm.storage.urllib.request.urlopen`, and `zotrm.cron.subprocess.run`. mypy treats the live
pyzotero client as `Any` (no stubs); keep that boundary.

## Releasing

Push a `vX.Y.Z` tag → `.github/workflows/release.yml` builds and publishes to PyPI via
trusted publishing (OIDC, no tokens). Bump `version` in `pyproject.toml` + update
`CHANGELOG.md` first; the tag and version must match. Versions are immutable on PyPI.
