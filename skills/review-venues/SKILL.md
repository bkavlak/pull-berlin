---
name: review-venues
description: Help a person check the Berlin evening-spaces catalog by hand and send their answers as a pull request. Use when someone wants to review, validate, verify, correct or improve the venue data or the map, says a venue on the map is wrong, or asks how to contribute data to pull-berlin.
---

# Review venues (human-in-the-loop data contribution)

The person only judges. You do everything else: setup, running Laya, showing the evidence,
recording answers, and the pull request. This works with any agent that can run shell commands in
this repository, on macOS, Linux or Windows.

What the person decides, per venue, for three claims:

| short name | question for the person |
|---|---|
| `rentable` | Can you rent this place, or a room in it, for your own private event (party, wedding, company event)? |
| `hosts` | Does it run its own public evening events (concerts, club nights, parties, readings, screenings)? |
| `late` | Is it open, or do its events go on, past midnight? |

Answers are `yes`, `no` or `unsure`. They are stored in `data/reviews/<github-login>.jsonl` and
become evidence on the public map once the pull request is merged.

## Ground rules

- **The person's answer is the data.** Never answer for them, never fill in from your own
  knowledge, never guess an ambiguous reply — ask again. You may open the venue's website or
  translate a passage when they ask.
- The pull request contains **only** `data/reviews/<login>.jsonl`. Do not change code, the catalog
  snapshot (`data/catalog/`), docs or anything else. CI rejects any other file.
- Do not edit review files by hand; `pull-berlin review record` writes them.
- Keep the person's effort small: one short message per venue, no walls of text.

## 1. Setup (once per machine; do it silently, report only problems)

Run everything from the repository root.

1. **Tools.** Needs `git`, [`uv`](https://docs.astral.sh/uv/) and Python ≥ 3.10.
   - No `uv`: macOS/Linux `curl -LsSf https://astral.sh/uv/install.sh | sh`;
     Windows `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`.
   - No suitable Python: if `asdf` is installed run `asdf install`; otherwise
     `UV_PYTHON_DOWNLOADS=automatic uv python install 3.12` (tell the person this downloads Python).
2. **Laya.** `uv sync --extra laya`. The first `review next` downloads the Laya model; say so once
   ("first run downloads the Laya model, this takes a few minutes"). If Laya cannot be installed
   or run on this machine, use `--classifier keywords` for the rest of the session and tell the
   person in one line that the keyword reader is standing in for Laya.
3. **Who is reviewing.** Their GitHub login names the file and must match the pull request author.
   Try `gh api user -q .login`; if that fails, ask once: "What's your GitHub user name?".
   Pass it as `--reviewer <login>` (or set `PULL_BERLIN_REVIEWER`).
4. **Fresh branch from the latest catalog.**
   ```bash
   git fetch origin
   git switch -c reviews/<login>-<yyyy-mm-dd> origin/main
   ```
   If the working tree has unrelated changes, stash them or ask before touching anything.

## 2. The review loop

Get the next venue — the one the catalog is least sure about:

```bash
uv run pull-berlin review next --reviewer <login>
```

If the person names a venue ("Kater Blau is wrong"), check that one instead:
`uv run pull-berlin review next --reviewer <login> --facility "kater blau"` (an id or part of the
name; several matches come back as a list — let them pick).

The command prints JSON: `name`, `category`, `links` (OpenStreetMap, website), and per claim in
`checks`: `question`, `catalog_confidence` (0–1, the map shows an offering from 0.60), `sources`
(what each source says now), and what Laya read on the website: `model_probability`, `passage`,
`passage_url`. `{"done": true}` means nothing is left.

Show it like this (translate German passages into the person's language in a short gist, keep a
short original quote):

> **Festsaal Kreuzberg** · event hall · [website](…) · [OSM](…)
>
> 1. **Rentable for private events?** Map now: yes (0.80, from OSM). Laya: 0.93 on /mieten —
>    "Unser Saal kann für Hochzeiten und Firmenfeiern gemietet werden" (rooms for weddings and
>    company parties).
> 2. **Own public evening events?** Map now: no (0.00). Laya found nothing.
> 3. **Open past midnight?** Map now: 0.64 (OSM opening hours). Laya: 0.12.
>
> Reply e.g. `yes no unsure`, or `skip`, or `stop`.

Then record exactly what they said (an optional note in their words if they gave a reason):

```bash
uv run pull-berlin review record --reviewer <login> --facility <id> \
  --rentable yes --hosts no --late unsure --note "Booking form on /mieten"
```

It prints the effect on the map, e.g. `Festsaal Kreuzberg: event_rental 0.80 (evening) -> event_rental 1.00 (evening)`.
Pass that line on, then continue with the next venue.

- `skip` → `uv run pull-berlin review skip --reviewer <login> --facility <id>` (stays local).
- All three unsure → nothing to record; treat it as a skip.
- Changed their mind about an earlier venue → record it again; the last answer counts.
- `stop` / "that's enough" → go to step 3.

## 3. Send the pull request

1. Check and summarise:
   ```bash
   uv run pull-berlin review check
   uv run pull-berlin review summary --reviewer <login> > "${TMPDIR:-/tmp}/pr-body.md"
   ```
2. Commit only the review file and verify nothing else is staged:
   ```bash
   git add data/reviews/<login>.jsonl
   git diff --cached --name-only        # must print exactly data/reviews/<login>.jsonl
   git commit -m "Reviews by @<login>: <n> venues"
   ```
3. Push and open the PR against `bkavlak/pull-berlin`, `main`:
   - With the GitHub CLI (`gh auth status` works):
     ```bash
     gh repo fork --remote --remote-name fork   # skip if origin is already writable by them
     git push -u fork HEAD
     gh pr create --repo bkavlak/pull-berlin --base main \
       --title "Reviews by @<login>: <n> venues" --body-file "${TMPDIR:-/tmp}/pr-body.md"
     ```
   - Without it: ask the person to click **Fork** on https://github.com/bkavlak/pull-berlin (the one
     thing they must do themselves), then
     `git remote add fork https://github.com/<login>/pull-berlin.git && git push -u fork HEAD`
     and give them the link
     `https://github.com/bkavlak/pull-berlin/compare/main...<login>:pull-berlin:<branch>?expand=1`
     with the summary to paste as the description.
4. Tell them in two lines: how many venues they checked, what changes on the map, the PR link.
   After merge the public map updates by itself.

## Optional: see the effect locally

```bash
uv run pull-berlin publish && uv run pull-berlin serve   # http://127.0.0.1:8000/
```

`publish` writes to `data/published/` (ignored by git); venues they checked say "Checked by @login".
