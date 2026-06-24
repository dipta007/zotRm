# Advanced usage

For everyday setup, see the [README](../README.md). This page covers the details power
users may want.

## How state is tracked

zotrm keeps no database. It records progress entirely in two Zotero tags on each item:

- `rm:synced` — the paper has been pushed to the tablet.
- `rm:annotated` — the marked-up copy has been pulled back into Zotero.

This makes every command idempotent: run them as often as you like (or from cron) and
nothing is pushed or pulled twice.

## The config file

Settings live at `~/.config/zotrm/config.ini`. The `zotrm config` wizard writes it for
you, but you can edit it by hand or point at a different file with `--config`.

```ini
[zotero]
library_id   = 1234567
api_key      = your-zotero-api-key
library_type = user
# Optional: point at your local Zotero storage to avoid re-downloading PDFs.
storage_dir  = /Users/you/Zotero/storage

[remarkable]
# The Zotero collection whose items get pushed to the tablet.
collection            = reMarkable
# Folder on the reMarkable where papers land (created if missing).
folder                = /Papers
# Recreate Zotero sub-collections as nested folders on the tablet?
mirror_subcollections = true
# Where annotated PDFs are written locally when pulled back.
output_dir            = /Users/you/Zotero/annotated
# Re-attach the annotated PDF to the Zotero item? (needs Zotero file storage)
reattach              = true
```

### Settings reference

| Section       | Key                     | Default                 | Meaning                                                        |
| ------------- | ----------------------- | ----------------------- | -------------------------------------------------------------- |
| `zotero`      | `library_id`            | _(required)_            | Your Zotero userID (or group ID).                              |
| `zotero`      | `api_key`               | _(required)_            | A private key with read **and write** access.                  |
| `zotero`      | `library_type`          | `user`                  | `user` or `group`.                                             |
| `zotero`      | `storage_dir`           | _(none)_                | Local Zotero storage; lets push skip re-downloading PDFs.      |
| `remarkable`  | `collection`            | _(required)_            | Name of the Zotero collection to sync.                         |
| `remarkable`  | `folder`                | `/Papers`               | Destination folder on the tablet.                              |
| `remarkable`  | `mirror_subcollections` | `true`                  | Recreate sub-collections as nested folders (vs. flat).         |
| `remarkable`  | `output_dir`            | `~/zotrm-annotated`     | Where pulled annotated PDFs are written.                       |
| `remarkable`  | `reattach`              | `true`                  | Re-attach the annotated PDF to the Zotero item.                |

Booleans accept `true`/`false`, `1`/`0`, or `yes`/`no`.

`zotrm config --show` prints the current location and values (the API key is masked).

## Global flags

- `--dry-run` — show what each command would do without changing anything. Works on every
  subcommand: `zotrm --dry-run sync`.
- `--config PATH` — use a config file somewhere other than the default. Handy for keeping
  several profiles:

  ```sh
  zotrm --config ~/work/zotrm.ini push
  zotrm --config ~/personal/zotrm.ini push
  ```

## Sub-collection mirroring

With `mirror_subcollections = true`, the Zotero collection's sub-collections are recreated
as nested folders on the tablet. For example, a paper inside
`reMarkable › Multimodal › Retrieval` lands in `/Papers/Multimodal/Retrieval`. With it set
to `false`, every paper lands flat in `folder`.

## Scheduled sync (cron internals)

`zotrm cron` writes a single line into your user crontab, tagged with a `# zotrm-sync`
marker so re-running replaces it instead of adding duplicates. A typical line:

```
0 * * * * /Users/you/.local/bin/zotrm sync >> /Users/you/.config/zotrm/sync.log 2>&1  # zotrm-sync
```

- Output (and any errors) go to `~/.config/zotrm/sync.log`.
- `zotrm cron --show` prints the current line; `zotrm cron --remove` deletes it.
- Inspect or edit it directly any time with `crontab -l` / `crontab -e`.

If the `zotrm` command isn't found on `PATH` at scheduling time, the job falls back to
`python -m zotrm`, which the package also supports.

cron is the only scheduler supported (macOS and Linux). launchd/systemd are out of scope.

## Running without installing

The package is runnable as a module, which is what the cron fallback uses:

```sh
python -m zotrm status
```

## Troubleshooting

- **`rmapi not found on PATH`** — install the ddvk fork (`brew install rmapi`) and make
  sure a new shell can see it.
- **Zotero check fails in the wizard** — usually a mistyped `library_id`/`api_key`, or the
  key lacks write access. You can still save and fix it later.
- **`crontab not found`** — `zotrm cron` needs cron, available on macOS and Linux.
- **Nothing comes back on pull** — the tablet must be online and synced to the reMarkable
  cloud, and two-way document sync requires a reMarkable Connect subscription. Also
  remember annotations only return as a flattened PDF, never as editable Zotero
  highlights.

## Publishing to PyPI (for maintainers)

1. Bump `version` in `pyproject.toml` (PyPI rejects re-uploading a version).
2. Build fresh artifacts:

   ```sh
   rm -rf dist && uv build
   ```

3. Get an API token from <https://pypi.org/manage/account/token/>.
4. Try **TestPyPI** first (a safe practice copy of PyPI):

   ```sh
   uv publish --publish-url https://test.pypi.org/legacy/ --token <test-token>
   ```

5. When happy, publish for real:

   ```sh
   uv publish --token <pypi-token>
   ```

   (Or set `export UV_PUBLISH_TOKEN=<token>` once and just run `uv publish`.)

After it is live, anyone can install it with `uv tool install zotrm`.
```
