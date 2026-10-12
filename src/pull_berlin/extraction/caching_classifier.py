"""Remembers judgements per (model, question-set version, text) in an append-only JSONL file."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

from pull_berlin.catalog.domain.claim import ClaimType, Proposition
from pull_berlin.catalog.domain.values import SpaceCategory
from pull_berlin.extraction.ports import Judgement, TextClassifier


class CachingClassifier:
    def __init__(self, inner: TextClassifier, path: Path, question_version: str) -> None:
        self._inner = inner
        self._path = path
        self._salt = f"{inner.model_id}|{question_version}|"
        self._known: dict[str, Judgement] = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                record = json.loads(line)
                self._known[record["key"]] = _decode(record["judgement"])

    @property
    def model_id(self) -> str:
        return self._inner.model_id

    def classify(self, texts: Sequence[str]) -> list[Judgement]:
        keys = [self._key(text) for text in texts]
        missing = list(
            dict.fromkeys(text for text, key in zip(texts, keys, strict=True) if key not in self._known)
        )
        if missing:
            fresh = self._inner.classify(missing)
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as log:
                for text, judgement in zip(missing, fresh, strict=True):
                    key = self._key(text)
                    self._known[key] = judgement
                    log.write(json.dumps({"key": key, "judgement": _encode(judgement)}) + "\n")
        return [self._known[key] for key in keys]

    def _key(self, text: str) -> str:
        return hashlib.sha256((self._salt + text).encode()).hexdigest()


def _encode(judgement: Judgement) -> dict[str, float]:
    return {
        p.claim_type.value + (f":{p.category.value}" if p.category else ""): v for p, v in judgement.items()
    }


def _decode(raw: dict[str, float]) -> Judgement:
    judgement: dict[Proposition, float] = {}
    for label, value in raw.items():
        claim_type, _, category = label.partition(":")
        judgement[Proposition(ClaimType(claim_type), SpaceCategory(category) if category else None)] = value
    return judgement
