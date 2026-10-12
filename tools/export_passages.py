"""Exports passages from the cached venue sites as unlabelled JSONL, ready for labelling.

    uv run python tools/export_passages.py [--cache data/cache] [--out eval/candidates.jsonl]

Label each line by setting every value in "labels" to true or false (null = not judged), set
"labelled_by", then move finished lines into eval/gold/<name>.jsonl.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pull_berlin.extraction.questions import QUESTION_SET_V1
from pull_berlin.sources.venue_site import passages, read_html


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, default=Path("data/cache"))
    parser.add_argument("--out", type=Path, default=Path("eval/candidates.jsonl"))
    args = parser.parse_args()

    seen: set[str] = set()
    lines = []
    for path in sorted((args.cache / "site").glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record["url"].endswith("/robots.txt"):
            continue
        for passage in passages(read_html(record["content"], record["url"]).text, record["url"], 1500, 3):
            if passage.text not in seen:
                seen.add(passage.text)
                labels = {q.key: None for q in QUESTION_SET_V1.yes_no}
                lines.append(
                    {"url": passage.url, "text": passage.text, "labels": labels, "labelled_by": None}
                )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines), encoding="utf-8"
    )
    print(f"wrote {len(lines)} passages to {args.out}")


if __name__ == "__main__":
    main()
