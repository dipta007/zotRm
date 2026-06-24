# zotrm

[![CI](https://github.com/dipta007/zotRm/actions/workflows/ci.yml/badge.svg)](https://github.com/dipta007/zotRm/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/zotrm.svg)](https://pypi.org/project/zotrm/)
[![Python](https://img.shields.io/pypi/pyversions/zotrm.svg)](https://pypi.org/project/zotrm/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Read your Zotero papers on a **reMarkable Paper Pro**, then get your handwritten
notes back into Zotero — with one command.

## Demo

![zotrm in action: push papers, annotate on the tablet, pull them back](docs/demo.gif)

> _Recording the GIF: see [how to record the demo](docs/advanced-usage.md#recording-the-demo-gif)._

**What it does, in plain words:**

- **push** — sends the PDFs from one Zotero collection to your reMarkable tablet.
- **pull** — brings the marked-up PDFs back and attaches them to the same Zotero papers.
- **status** — shows which papers are waiting, on the tablet, or already done.
- **sync** — does a pull and then a push, together.

You never push or pull the same paper twice by mistake — the tool remembers what it has
done. It is safe to run again and again.

> **One honest limit (this is reMarkable's behavior, not a bug here):**
> Your highlights and handwriting come back as part of the PDF image — "painted onto"
> the page. They do **not** come back as clickable Zotero highlights.

## Why zotrm?

If you read research papers on a reMarkable, getting them on and off the tablet is fiddly:
export each PDF, drag it into the reMarkable app, and later dig the annotated copy back
out and re-file it in Zotero. zotrm makes that **one command in each direction**, driven by
the collection you already curate in Zotero:

- **No manual file shuffling** — it reads your Zotero collection and uploads the PDFs for you.
- **Folders match your library** — Zotero sub-collections become nested folders on the tablet.
- **Nothing pushed or pulled twice** — progress is tracked with Zotero tags, so it's safe to
  re-run or schedule with `zotrm cron`.
- **No extra database or account** — just your Zotero API key and the `rmapi` tool.

It's a small, focused CLI — not a sync daemon or a cloud service.

---

## Before you start (what you need)

1. A **Zotero** account with some PDFs in it.
2. A **reMarkable** tablet, turned on and connected to WiFi.
3. A **reMarkable Connect** subscription — this is what lets files move to and from the
   tablet over the internet. Without it, push and pull may not work.
4. A computer (Mac or Linux) where you can open a **Terminal** (a window where you type
   commands). On a Mac, open the app called **Terminal**.

You will copy and paste a few commands. That is all.

---

## Setup (about 10 minutes)

### Step 1 — Install `uv`

`uv` installs this tool for you. Paste this into the Terminal and press Enter:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Close the Terminal and open it again so the change takes effect.

### Step 2 — Install `rmapi` and connect it to your tablet

`rmapi` is a separate program that talks to your reMarkable:

```sh
brew install rmapi
```

(No Homebrew? See <https://github.com/ddvk/rmapi> for other ways. Use the **ddvk**
version — the original does not work with new tablets.)

Now connect it to your tablet **one time**:

```sh
rmapi
```

It shows a web address and asks for a code. Open
<https://my.remarkable.com/device/desktop>, copy the code shown there, and paste it into
the Terminal. Done — you won't do this again.

### Step 3 — Install `zotrm`

```sh
uv tool install zotrm
```

### Step 4 — Set up your account (answer a few questions)

Just run:

```sh
zotrm config
```

It asks you a few simple questions (use the arrow keys and Enter), then checks that your
details work. To answer the two Zotero questions:

- Open <https://www.zotero.org/settings/keys>.
- Your **library ID** is the number shown as "Your userID".
- Click **Create new private key**, allow read **and write**, and copy the key it gives
  you.

> **Tip:** In Zotero, make a collection (for example named `reMarkable`) and drag the
> papers you want to read into it. Give that same name when the wizard asks for the
> collection.

That's it — your settings are saved automatically. (The very first time you run any
command, this wizard starts on its own if you haven't set up yet.)

### Step 5 — Use it

Send your papers to the tablet:

```sh
zotrm push
```

Read and annotate them on the reMarkable. When you're done, bring them back:

```sh
zotrm pull
```

That's the whole loop. 🎉

### Step 6 (optional) — Make it automatic

Want it to sync by itself on a schedule? Run:

```sh
zotrm cron
```

Pick how often (every hour, daily, etc.) and it sets everything up for you. Remove it
later with `zotrm cron --remove`.

---

## Everyday commands

```sh
zotrm push      # send waiting papers to the tablet
zotrm pull      # bring marked-up papers back into Zotero
zotrm status    # see what is waiting / on the tablet / done
zotrm sync      # pull, then push, in one step

zotrm config    # change your settings any time
zotrm cron      # set up (or change) automatic syncing
```

Not sure what a command will do? Add `--dry-run` to see without changing anything:

```sh
zotrm --dry-run push
```

---

## If something goes wrong

- **"rmapi not found"** → Step 2 was missed, or reopen the Terminal.
- **"config not found"** → Run `zotrm config` to set up your account.
- **"no Zotero collection named ..."** → The collection name in your settings doesn't
  exactly match a collection in Zotero. Check spelling and capital letters
  (`zotrm config --show` prints your current settings).
- **Pull finds nothing** → Make sure the tablet is online and finished syncing, and that
  you have a reMarkable Connect subscription.

Run any command with `--dry-run` first if you're unsure — it changes nothing.

---

## FAQ

**Do I need a reMarkable Connect subscription?**
Yes, in practice. `zotrm` talks to the reMarkable **cloud** through `rmapi`, and two-way
document sync (uploading PDFs and downloading annotated ones) needs Connect.

**Why don't my highlights come back as real Zotero highlights?**
The reMarkable returns a flattened PDF — your marks are baked into the page image. That's a
reMarkable limitation, not something `zotrm` can change. You get a faithful annotated PDF
re-attached to the item, just not editable highlight objects.

**Does it duplicate files if I run it again?**
No. It tags items `rm:synced` once pushed and `rm:annotated` once pulled back, and skips
anything already done. Re-run it (or schedule it) freely.

**Can I use it with more than one Zotero library?**
Yes — keep separate config files and pass `--config`. See
[advanced usage](docs/advanced-usage.md#global-flags).

**Does it work on Windows?**
Not currently. `zotrm` targets macOS and Linux (the `cron` scheduler is Unix-only).

**Is my Zotero API key safe?**
It's stored only in your local config file (`~/.config/zotrm/config.ini`) and never sent
anywhere except Zotero's own API. `zotrm config --show` masks it.

---

## More

- **[Advanced usage](docs/advanced-usage.md)** — editing the config file by hand, the full
  settings reference, how the scheduled sync works, multiple configs, and deeper
  troubleshooting.
- **[Contributing](CONTRIBUTING.md)** — set up the project for development and run the
  tests.

## License

MIT — see [LICENSE](LICENSE).
