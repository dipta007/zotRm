# zotrm

[![CI](https://github.com/dipta007/zotRm/actions/workflows/ci.yml/badge.svg)](https://github.com/dipta007/zotRm/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/zotrm.svg)](https://pypi.org/project/zotrm/)
[![Python](https://img.shields.io/pypi/pyversions/zotrm.svg)](https://pypi.org/project/zotrm/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/dipta007/zotRm/blob/main/LICENSE)

Read your Zotero papers on a **reMarkable Paper Pro**, then get your handwritten
notes back into Zotero — with one command.

## Demo

![zotrm in action: push papers, annotate on the tablet, pull them back](https://raw.githubusercontent.com/dipta007/zotRm/main/docs/demo.gif)

> _Recording the GIF: see [how to record the demo](https://github.com/dipta007/zotRm/blob/main/docs/advanced-usage.md#recording-the-demo-gif)._

**What it does, in plain words:**

- **`zotrm sync`** — the whole workflow in one command. The first time it sees a paper it
  sends the PDF from your Zotero collection to the tablet. After that, each run brings your
  annotations back into Zotero as a single, always-current `… (annotated).pdf` — your
  original is never touched, and nothing is duplicated.
- **`zotrm status`** — shows which papers are waiting, on the tablet, or annotated.

It remembers what it has done (using Zotero tags), so it's safe to run again and again —
great for a cron schedule.

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

### Step 4 — Set up your account

A friendly wizard fills in your settings for you. First grab two things from Zotero, then
run it.

**4a. Get your Zotero details** (about a minute)

Open <https://www.zotero.org/settings/keys> and log in. You need two things from this page:

1. **Your library ID** — near the top it reads *"Your userID for use in API calls is
   **1234567**."* That number is your library ID.
2. **An API key** — click **Create new private key**, give it a name, tick **Allow library
   access** with **both read and write** (write lets `zotrm` save tags and attach your
   annotated PDFs), click **Save Key**, and **copy the key** — you can't see it again later.

**4b. Make a collection to sync** (recommended)

In the Zotero app, create a collection — say, named `reMarkable` — and drag in a few papers
you want to read. `zotrm` only ever touches papers in this one collection. Start with a
**throwaway collection of 1–2 papers** while you try things out.

**4c. Run the wizard**

```sh
zotrm config
```

Use the arrow keys ↑↓ to choose and Enter to confirm. Here is every question and what to
put:

| Question | What to enter |
| --- | --- |
| **Zotero library ID** | The userID number from step 4a. |
| **Zotero API key** | The key from step 4a (hidden as you type/paste). |
| **Library type** | `user` — choose `group` only for a shared group library. |
| **Local Zotero storage dir** _(optional)_ | Where the Zotero app keeps your PDFs, usually `~/Zotero/storage`. Lets `zotrm` read files from disk instead of re-downloading. Press Enter to skip if unsure. |
| **Zotero collection to sync** | The collection name from step 4b (e.g. `reMarkable`) — must match exactly, capitals included. |
| **reMarkable folder** | Where papers land on the tablet, e.g. `/Papers` (created if missing). |
| **Mirror sub-collections?** | `Yes` recreates your Zotero sub-collections as nested folders on the tablet; `No` puts everything in one folder. |
| **Where to save annotated PDFs** | A folder on your computer for the marked-up copies, e.g. `~/Zotero/annotated`. |
| **Where to store the annotated copy** | `zotero` = Zotero's own storage (uses your Zotero quota); `webdav` = your own WebDAV server (it then asks for the URL + login); `none` = keep it only as a local file, don't put it back in Zotero. |

When you finish, it checks your details (you'll see `✓ Zotero connection OK`), warns if
`rmapi` is missing, and saves everything to `~/.config/zotrm/config.ini`.

> The wizard also starts on its own the first time you run any command before setting up.
> To change settings later, run `zotrm config` again; to see what's saved (API key masked),
> run `zotrm config --show`.

### Step 5 — Use it

One command does everything:

```sh
zotrm sync
```

The **first** time, it sends your papers to the tablet. Read and annotate them on the
reMarkable, then run `zotrm sync` **again** — it pulls your annotations back into Zotero as a
single, always-up-to-date `… (annotated).pdf`. Your original PDF is never touched, and
re-running just refreshes that one annotated copy (no duplicates). That's the whole loop. 🎉

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
zotrm sync      # the whole workflow: push new papers, refresh annotations
zotrm status    # see what is waiting / on the tablet / annotated

zotrm config    # change your settings any time
zotrm cron      # run sync automatically on a schedule
```

Not sure what a command will do? Add `--dry-run` to see without changing anything:

```sh
zotrm --dry-run sync
```

---

## If something goes wrong

- **"rmapi not found"** → Step 2 was missed, or reopen the Terminal.
- **"config not found"** → Run `zotrm config` to set up your account.
- **"no Zotero collection named ..."** → The collection name in your settings doesn't
  exactly match a collection in Zotero. Check spelling and capital letters
  (`zotrm config --show` prints your current settings).
- **Sync brings nothing back** → Make sure the tablet is online and finished syncing, that
  you've actually annotated the paper, and that you have a reMarkable Connect subscription.
- **`File would exceed quota`** → Your Zotero storage is full. Switch the annotated copy to
  WebDAV or `none`: run `zotrm config` and change "Where to store the annotated copy."

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
No. It keeps exactly **one** `… (annotated).pdf` per paper and overwrites it on each sync,
and it never re-uploads your original. Re-run `zotrm sync` (or schedule it) freely.

**Where does the annotated copy get stored?**
Your choice, set during `zotrm config`: `zotero` (Zotero's own storage, uses your quota),
`webdav` (your own WebDAV server — same files/login Zotero uses), or `none` (keep it only
as a local file). A local copy is always saved to your `output_dir` regardless.

**Can I use it with more than one Zotero library?**
Yes — keep separate config files and pass `--config`. See
[advanced usage](https://github.com/dipta007/zotRm/blob/main/docs/advanced-usage.md#global-flags).

**Does it work on Windows?**
Not currently. `zotrm` targets macOS and Linux (the `cron` scheduler is Unix-only).

**Is my Zotero API key safe?**
It's stored only in your local config file (`~/.config/zotrm/config.ini`) and never sent
anywhere except Zotero's own API. `zotrm config --show` masks it.

---

## More

- **[Advanced usage](https://github.com/dipta007/zotRm/blob/main/docs/advanced-usage.md)** —
  editing the config file by hand, the full settings reference, how the scheduled sync
  works, multiple configs, and deeper troubleshooting.
- **[Contributing](https://github.com/dipta007/zotRm/blob/main/CONTRIBUTING.md)** — set up
  the project for development and run the tests.

## License

MIT — see [LICENSE](https://github.com/dipta007/zotRm/blob/main/LICENSE).
