# zotrm

[![CI](https://github.com/dipta007/zotrm/actions/workflows/ci.yml/badge.svg)](https://github.com/dipta007/zotrm/actions/workflows/ci.yml)

Read your Zotero papers on a **reMarkable Paper Pro**, then get your handwritten
notes back into Zotero — with one command.

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

## More

- **[Advanced usage](docs/advanced-usage.md)** — editing the config file by hand, the full
  settings reference, how the scheduled sync works, multiple configs, and deeper
  troubleshooting.
- **[Contributing](CONTRIBUTING.md)** — set up the project for development and run the
  tests.

## License

MIT — see [LICENSE](LICENSE).
