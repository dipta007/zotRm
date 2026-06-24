# Contributing to zotrm

Thanks for your interest in improving zotrm! This project uses
[uv](https://docs.astral.sh/uv/) for everything.

## Set up for development

```sh
git clone https://github.com/dipta007/zotrm
cd zotrm
uv sync              # creates .venv and installs deps + dev tools
uv pip install -e .  # editable install, so `zotrm` reflects your edits
```

## Project layout

```
src/zotrm/
  cli.py          # argparse, main(), command dispatch
  config.py       # config loading/validation + shared helpers
  zotero.py       # pyzotero wrapper: collection walk, tag helpers
  remarkable.py   # rmapi subprocess wrapper
  wizard.py       # interactive `zotrm config` setup wizard
  cron.py         # `zotrm cron` schedule builder + crontab management
  __main__.py     # enables `python -m zotrm`
tests/            # pytest suite (pyzotero + rmapi + questionary are mocked)
```

## Run the checks

All four must pass before a change is ready:

```sh
uv run pytest          # tests
uv run ruff check .    # lint
uv run ruff format .   # format (use --check in CI)
uv run mypy src        # type-check (strict)
```

## Code style

- **Formatting & linting:** `ruff`, line length 100. Run `ruff format` before committing.
- **Types:** full type hints; `mypy --strict` must pass on `src`. The live `pyzotero`
  client is typed as `Any` (it ships no stubs); helpers pin down the slices we use.
- **Tests:** external systems are never hit. `pyzotero.Zotero`, the `rmapi`/`crontab`
  subprocesses, and `questionary` prompts are all replaced with fakes (see
  `tests/conftest.py`). Favor meaningful coverage over a coverage number.
- **Keep changes surgical.** Match the surrounding style; don't refactor unrelated code.

## Making a change

1. Branch off `main`.
2. Add or update tests alongside your change.
3. Make sure all four checks above are green.
4. Open a pull request describing what changed and why.

## Releasing

See [docs/advanced-usage.md](docs/advanced-usage.md#publishing-to-pypi-for-maintainers)
for how to publish a new version to PyPI.
