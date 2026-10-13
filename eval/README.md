# Evaluation data

`gold/*.jsonl` — labelled passages, one JSON object per line:
`{"url", "text", "labels": {"is_rentable_for_private_events": true|false|null, ...}, "labelled_by"}`.
A label says whether **the text itself states** the proposition; `null` means not judged.

- `gold/human-2026-10-12.jsonl`: 51 passages labelled by the project owner on the labelling page
  (replaces the earlier Claude-labelled silver set, which covered the same passages). Few positives for
  `hosts_evening_events` (2) and `operates_past_midnight` (3): only rentability is measurable yet.

Labelling page: the **Venue Passage Labels** artifact on claude.ai holds the 141 exported passages
(Claude's silver labels shown as drafts on the first 50). Label there with Y / N / U, then ask Claude to
read the labels back into `gold/human-<date>.jsonl` (or use the page's "Copy labels as JSONL").

Human reviews (`data/reviews/*.jsonl`, see `skills/review-venues/`) keep the passage Laya rated highest
and its probability next to the reviewer's yes/no, so they are a growing source of reviewed labels for
fine-tuning. Note they judge the *facility*, not only the passage.

Workflow: `uv run python tools/export_passages.py` writes unlabelled candidates to `eval/candidates.jsonl`
(ignored by git); label them, move finished lines into `gold/`, then
`uv run --extra laya python tools/eval_classifiers.py`.

Source texts are excerpts of public websites, kept for evaluation only.

## Results — 2026-10-12, silver set, `is_rentable_for_private_events` (47 judged, 16 positive)

| classifier | precision | recall | F1 | Brier |
|---|---|---|---|---|
| keywords (`keywords-v1`) | **1.00** | 0.69 | **0.81** | **0.109** |
| Laya 0.4.6 multilingual, zero-shot | 0.41 | 1.00 | 0.58 | 0.385 |
| Laya + lexical gate | 0.55 | 1.00 | 0.71 | 0.236 |
| Laya, multiple-choice "what does the text offer" | 0.67 | 0.12 | 0.21 | — |

Findings:
- Zero-shot Laya over-claims and is not calibrated on web text (p≈0.999 "rentable" for bank pension and
  home-care pages); raising the threshold does not fix it (best F1 0.73 at 0.8 with the gate).
- The lexical gate helps (Brier 0.385 → 0.236) and costs no recall.
- Keywords are the default classifier until a fine-tuned Laya beats them on a human-reviewed set.
- Next: review/extend the labels to a few hundred passages, fine-tune Laya (its Apple Silicon script),
  re-run this table. Other propositions need more positives before their numbers mean anything.

## Results — 2026-10-12, human labels (51), keyword classifier v1 → v2

| | precision | recall | F1 | Brier |
|---|---|---|---|---|
| rentable, `keywords-v1` | 1.00 | 0.65 | 0.79 | 0.127 |
| rentable, `keywords-v2` | 1.00 | 0.71 | **0.83** | **0.107** |
| hosting false positives (2 true in set) | v1: 11 | v2: 3 | | Brier 0.248 → 0.101 |

v2 adds bar vocabulary (geschlossene Gesellschaft, Separee, Hinterzimmer, Nebenraum für Feiern, quiz,
karaoke, open mic, jam session, comedy, DJ) and drops "party", "programm", "tickets", "theater" from hosting.
Known ambiguity left in: "DJ" on rental pages ("DJ included in the package").
