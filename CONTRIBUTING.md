# Contributing

## Check the data (no coding needed)

The map at https://bkavlak.github.io/pull-berlin/ is built by machines reading OpenStreetMap and
venues' websites — with a local model, [Laya](https://github.com/NandhaKishorM/laya). Machines get
things wrong. You can fix that by answering three questions per venue:

- Can you rent it for a private event?
- Does it run its own public evening events?
- Is it open (or do events go on) past midnight?

Your AI assistant does the rest: installing, running Laya on the venue's website, showing you what
it found, saving your answers and opening the pull request.

1. Clone the repository and open it in any AI coding agent that can run commands
   (Claude Code, Codex, Cursor, Gemini CLI, …):
   ```bash
   git clone https://github.com/bkavlak/pull-berlin.git && cd pull-berlin
   ```
2. Say: **"I want to review Berlin venues."** (Or: "Kater Blau is wrong on the map.")
3. Answer `yes`, `no` or `unsure` for each venue it shows you. Say `stop` when you've had enough.
4. It opens a pull request containing only your answers (`data/reviews/<your-login>.jsonl`).
   After merge the map updates by itself and your venues say "Checked by @you".

You need a GitHub account. The agent follows [`skills/review-venues/SKILL.md`](skills/review-venues/SKILL.md);
you can also run the same steps yourself from that file.

## Change the code

Read [`AGENTS.md`](AGENTS.md) and the rules it links (APOSD, DDD, TDD, tooling) first; checks are in the
README. Keep code changes and data reviews in separate pull requests.
