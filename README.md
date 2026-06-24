# zotrm-bridge

Read your Zotero papers on a **reMarkable Paper Pro**, then get your handwritten
notes back into Zotero — with one command.

**What it does, in plain words:**

- **push** — sends the PDFs from one Zotero collection to your reMarkable tablet.
- **pull** — brings the marked-up PDFs back and attaches them to the same Zotero papers.
- **status** — shows which papers are waiting, on the tablet, or already done.
- **sync** — does a pull and then a push, together.

You never push or pull the same paper twice by mistake. The tool remembers what it
has done using two Zotero tags (`rm:synced` and `rm:annotated`), so it is safe to run
again and again.

> **One honest limit (this is reMarkable's behavior, not a bug here):**
> Your highlights and handwriting come back as part of the PDF image — "painted onto"
> the page. They do **not** come back as clickable Zotero highlights.

---

## Before you start (what you need)

1. A **Zotero** account with some PDFs in it.
2. A **reMarkable** tablet that is turned on and connected to WiFi.
3. A **reMarkable Connect** subscription. This is what lets files move to and from the
   tablet over the internet. Without it, push and pull may not work.
4. A computer (Mac or Linux) where you can open a **Terminal** (a window where you type
   commands). On a Mac, open the app called **Terminal**.

You will copy and paste a few commands. That is all.

---

## Setup (about 10 minutes)

### Step 1 — Install `uv`

`uv` is a small helper that installs this tool for you. Paste this into the Terminal and
press Enter:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Close the Terminal and open it again so the change takes effect.

### Step 2 — Install `rmapi` and connect it to your tablet

`rmapi` is a separate program that talks to your reMarkable. Install it:

```sh
brew install rmapi
```

(No Homebrew? See <https://github.com/ddvk/rmapi> for other ways to install. Use the
**ddvk** version — the normal one does not work with new tablets.)

Now connect it to your tablet **one time**. Type:

```sh
rmapi
```

It will show you a web address and ask for a code. Open
<https://my.remarkable.com/device/desktop> in your browser, copy the code it gives you,
and paste it into the Terminal. Done — you won't need to do this again.

### Step 3 — Install `zotrm`

```sh
uv tool install zotrm-bridge
```

(If the tool is not on PyPI yet, download this project, go into its folder in the
Terminal, and run `uv tool install .` instead.)

Check it worked:

```sh
zotrm --help
```

### Step 4 — Make your settings file

The tool reads its settings from a file at `~/.config/zotrm/config.ini`.
Create that file and paste in the template below, then change the values to your own.

```ini
[zotero]
library_id   = 1234567
api_key      = your-zotero-api-key
library_type = user
# Optional. If you have Zotero on this computer, point here to skip re-downloading PDFs.
storage_dir  = /Users/you/Zotero/storage

[remarkable]
# The name of the Zotero collection you want to send to the tablet.
collection            = reMarkable
# The folder on the tablet where papers go. It is created if missing.
folder                = /Papers
# Copy your Zotero sub-collections as folders on the tablet? (true / false)
mirror_subcollections = true
# Where to save the marked-up PDFs on this computer when you pull them back.
output_dir            = /Users/you/Zotero/annotated
# Re-attach the marked-up PDF to the Zotero paper? (true / false)
reattach              = true
```

**Where to get your Zotero values:**

- Open <https://www.zotero.org/settings/keys>.
- Your **`library_id`** (called "Your userID") is shown there.
- Click **Create new private key**, allow read **and write**, and copy the key into
  **`api_key`**.

**Tip:** In Zotero, make a collection (for example named `reMarkable`) and drag the
papers you want to read into it. Put that same name in `collection` above.

### Step 5 — Use it

Send your papers to the tablet:

```sh
zotrm push
```

Go read and annotate them on the reMarkable. When you're done, bring them back:

```sh
zotrm pull
```

That's the whole loop. 🎉

---

## Everyday commands

```sh
zotrm push      # send waiting papers to the tablet
zotrm pull      # bring marked-up papers back into Zotero
zotrm status    # see what is waiting / on the tablet / done
zotrm sync      # pull, then push, in one step

# Want to see what WOULD happen, without changing anything? Add --dry-run:
zotrm --dry-run push

# Using a settings file in another place:
zotrm --config /path/to/other-config.ini status
```

---

## If something goes wrong

- **"rmapi not found"** → Step 2 was missed, or the Terminal needs to be reopened.
- **"config not found"** → The settings file in Step 4 is missing or in the wrong place.
  It must be at `~/.config/zotrm/config.ini`.
- **"no Zotero collection named ..."** → The `collection` name in your settings does not
  exactly match a collection in Zotero. Check spelling and capital letters.
- **Pull finds nothing** → Make sure the tablet is online and finished syncing, and that
  you have a reMarkable Connect subscription.

Run any command with `--dry-run` first if you are unsure — it changes nothing.

---

## For developers

```sh
uv sync                 # set up the project and dev tools
uv pip install -e .     # editable install
uv run pytest           # run the tests
uv run ruff check .     # lint
uv run ruff format .    # format
uv run mypy src         # type-check (strict)
uv build                # build the wheel + sdist into dist/
```

## For maintainers — publishing to PyPI

1. Make sure the version in `pyproject.toml` is new (PyPI rejects re-uploading a version).
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

   (Or set the token once as `export UV_PUBLISH_TOKEN=<token>` and just run `uv publish`.)

After it is live, anyone can install it with `uv tool install zotrm-bridge`.
