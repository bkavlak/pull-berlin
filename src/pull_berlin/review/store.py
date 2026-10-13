"""Review files on disk: `<dir>/<reviewer>.jsonl`, append-only, one review per line."""

from __future__ import annotations

from pathlib import Path

from pull_berlin.review.domain import Review, valid_reviewer


class ReviewFileError(ValueError):
    """A review file that cannot be read: bad JSON, a bad record, or someone else's name inside."""


class ReviewStore:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def path_for(self, reviewer: str) -> Path:
        return self._directory / f"{valid_reviewer(reviewer)}.jsonl"

    def append(self, review: Review) -> Path:
        path = self.path_for(review.reviewer)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as file:
            file.write(review.to_json() + "\n")
        return path

    def load(self, reviewer: str | None = None) -> list[Review]:
        """All reviews (or one reviewer's), in file order. Raises ReviewFileError naming file and line."""
        if not self._directory.exists():
            return []
        paths = [self.path_for(reviewer)] if reviewer else sorted(self._directory.glob("*.jsonl"))
        reviews = []
        for path in paths:
            if not path.exists():
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if not line.strip():
                    continue
                try:
                    review = Review.from_json(line)
                except ValueError as error:
                    raise ReviewFileError(f"{path}:{number}: {error}") from None
                if review.reviewer != path.stem:
                    raise ReviewFileError(
                        f"{path}:{number}: review by {review.reviewer!r} in {path.stem!r}'s file"
                    )
                reviews.append(review)
        return reviews
