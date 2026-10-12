"""Scores every available classifier on the labelled passages in eval/gold/*.jsonl.

    uv run python tools/eval_classifiers.py            # keywords only
    uv run --extra laya python tools/eval_classifiers.py   # + Laya, raw and gated

Laya answers are cached under data/cache/judgements, so re-running is cheap.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pull_berlin.catalog.domain.claim import ClaimType, Proposition
from pull_berlin.extraction.caching_classifier import CachingClassifier
from pull_berlin.extraction.evaluation import LabelledText, evaluate
from pull_berlin.extraction.gate import LexicalGate
from pull_berlin.extraction.keyword_classifier import KeywordClassifier
from pull_berlin.extraction.ports import TextClassifier
from pull_berlin.extraction.questions import QUESTION_SET_V1


def load_gold(directory: Path) -> list[LabelledText]:
    gold = []
    for path in sorted(directory.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            labels = {
                Proposition(ClaimType(key)): bool(value)
                for key, value in record["labels"].items()
                if value is not None
            }
            gold.append(LabelledText(text=record["text"], labels=labels, url=record.get("url", "")))
    return gold


def classifiers(cache: Path) -> dict[str, TextClassifier]:
    found: dict[str, TextClassifier] = {"keywords": KeywordClassifier()}
    try:
        from pull_berlin.extraction.laya_classifier import LayaClassifier

        laya = LayaClassifier()
    except ImportError:
        return found
    cached = CachingClassifier(laya, cache / "judgements" / f"{laya.model_id}.jsonl", QUESTION_SET_V1.version)
    found["laya"] = cached
    found["laya+gate"] = LexicalGate(cached)
    return found


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, default=Path("eval/gold"))
    parser.add_argument("--cache", type=Path, default=Path("data/cache"))
    args = parser.parse_args()

    gold = load_gold(args.gold)
    print(f"{len(gold)} labelled passages from {args.gold}\n")
    print(
        f"{'classifier':12s} {'proposition':32s} {'n':>4s} {'pos':>4s} {'pred':>5s} "
        f"{'prec':>5s} {'rec':>5s} {'f1':>5s} {'brier':>6s}"
    )
    for name, classifier in classifiers(args.cache).items():
        for s in evaluate(gold, classifier.classify([item.text for item in gold])):
            print(
                f"{name:12s} {s.proposition.label:32s} {s.n:4d} {s.positives:4d} {s.predicted_positives:5d} "
                f"{s.precision:5.2f} {s.recall:5.2f} {s.f1:5.2f} {s.brier:6.3f}"
            )


if __name__ == "__main__":
    main()
