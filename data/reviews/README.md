# Human reviews

One file per reviewer, named after their GitHub user name: `<github-login>.jsonl`.
Each line is one review of one facility, appended by `pull-berlin review record`:

```json
{"facility": "osm:node/123", "name": "Festsaal Kreuzberg", "reviewer": "ada", "reviewed_on": "2026-10-13",
 "verdicts": {"rentable": "yes", "hosts": "yes", "late": "unsure"},
 "note": "Booking form on /mieten",
 "model": "gated-laya-0.4.6-multilingual",
 "shown": {"rentable": {"url": "https://…/mieten", "probability": 0.93, "text": "…"}}}
```

- `verdicts`: `rentable` = can be rented for a private event, `hosts` = runs its own public evening
  events, `late` = open or events past midnight. `unsure` adds nothing.
- `shown`: the passage the model rated highest when the reviewer looked, with its probability —
  so the record doubles as a label for evaluating and fine-tuning Laya (`eval/`).
- If you review a facility again, your last line counts.

`pull-berlin publish` adds every review to the catalog snapshot (`data/catalog/facilities.json`)
as evidence of kind `human_review` (prior 0.98): a "no" takes a claim off the map, a "yes" puts it
on. The map on GitHub Pages is rebuilt from this folder on every merge to `main`.

Don't edit these files by hand — use the review skill: [`skills/review-venues/SKILL.md`](../../skills/review-venues/SKILL.md).
