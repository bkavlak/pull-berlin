"""Command line: `pull-berlin pull` runs every source and writes the exports."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from pull_berlin.application.publish import Change, changes, describe, publish, with_reviews
from pull_berlin.application.pull import pull
from pull_berlin.application.review import ReviewItem, choose_next, find, prepare
from pull_berlin.catalog.domain.facility import Facility
from pull_berlin.catalog.domain.values import SpaceCategory
from pull_berlin.extraction.caching_classifier import CachingClassifier
from pull_berlin.extraction.gate import LexicalGate
from pull_berlin.extraction.keyword_classifier import KeywordClassifier
from pull_berlin.extraction.ports import TextClassifier
from pull_berlin.extraction.questions import QUESTION_SET_V1
from pull_berlin.publishing.renderers import write_outputs
from pull_berlin.publishing.snapshot import read_snapshot
from pull_berlin.review.domain import REVIEWED_CLAIMS, Review, Verdict, valid_reviewer
from pull_berlin.review.store import ReviewFileError, ReviewStore
from pull_berlin.sources.osm_overpass import OsmOverpassSource
from pull_berlin.sources.venue_site import VenueSiteSource
from pull_berlin.sourcing.adapters import CachingFetcher, HttpFetcher
from pull_berlin.sourcing.ports import FetchError, SourceAdapter


def available_sources() -> list[SourceAdapter]:
    return [OsmOverpassSource()]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pull-berlin")
    commands = parser.add_subparsers(dest="command", required=True)
    pull_cmd = commands.add_parser("pull", help="fetch all sources and write CSV/JSON/GeoJSON")
    pull_cmd.add_argument("--out", type=Path, default=Path("data/out"))
    pull_cmd.add_argument(
        "--cache", type=Path, default=Path("data/cache"), help="raw document cache / recordings"
    )
    pull_cmd.add_argument(
        "--offline", action="store_true", help="use only cached documents, never the network"
    )
    pull_cmd.add_argument(
        "--all", action="store_true", help="also export facilities without an evening offering"
    )
    pull_cmd.add_argument(
        "--sites", action="store_true", help="also read each facility's own website (enrichment)"
    )
    pull_cmd.add_argument("--site-limit", type=int, default=None, help="enrich at most N facilities (sample)")
    pull_cmd.add_argument(
        "--classifier",
        choices=("laya", "laya-ungated", "keywords"),
        default="keywords",
        help="how website text is read: keyword baseline (default; best measured precision), Laya behind a "
        "lexical gate, or Laya on every passage (Laya needs `uv sync --extra laya`); see eval/README.md",
    )
    pull_cmd.add_argument(
        "--site-categories",
        default=None,
        help="read websites only of these kinds of place, comma-separated (e.g. bar or bar,club)",
    )
    pull_cmd.add_argument("--site-workers", type=int, default=8, help="websites visited in parallel")
    pull_cmd.add_argument(
        "--retry-failed", action="store_true", help="try websites again that failed in an earlier run"
    )
    pull_cmd.add_argument("--laya-batch-size", type=int, default=4, help="texts per Laya forward pass")
    publish_cmd = commands.add_parser(
        "publish", help="map data = catalog snapshot + human reviews -> data/published (what the site shows)"
    )
    _catalog_args(publish_cmd)
    publish_cmd.add_argument("--out", type=Path, default=PUBLISHED)
    serve_cmd = commands.add_parser("serve", help="open the map on localhost (web/ + data/published/)")
    serve_cmd.add_argument("--port", type=int, default=8000)
    serve_cmd.add_argument("--data", type=Path, default=PUBLISHED, help="folder with facilities.geojson")
    _review_parser(commands)
    args = parser.parse_args(argv)
    if args.command == "serve":
        return _serve(args.port, args.data)
    if args.command == "publish":
        return _publish(args)
    if args.command == "review":
        return _review(args)

    fetcher = CachingFetcher(
        args.cache, None if args.offline else HttpFetcher(), retry_failed=args.retry_failed
    )
    try:
        result = pull(
            available_sources(),
            fetcher,
            include_all=args.all,
            enrichers=[VenueSiteSource()] if args.sites else [],
            classifier=_classifier(args.classifier, args.cache, args.laya_batch_size) if args.sites else None,
            enrich_limit=args.site_limit,
            enrich_categories=_categories(args.site_categories),
            enrich_workers=args.site_workers,
        )
    except FetchError as error:
        print(f"fetch failed: {error}", file=sys.stderr)
        return 2

    written = write_outputs(result.facilities, args.out)
    report = result.report
    print(
        f"observations={report.observations} {report.observations_per_source} "
        f"outside_berlin={report.outside_berlin} facilities={report.facilities} in_scope={report.in_scope}"
    )
    if args.sites:
        print(
            f"sites attempted={report.sites_attempted} observed={report.sites_observed} "
            f"passages_classified={report.passages_classified}"
        )
    for path in written:
        print(f"wrote {path}")
    return 0


def _categories(value: str | None) -> set[SpaceCategory] | None:
    if not value:
        return None
    return {SpaceCategory(name.strip()) for name in value.split(",") if name.strip()}


def _serve(port: int, data: Path) -> int:
    from pull_berlin.serve import make_server

    if not Path("web/index.html").exists():
        print("run this from the project root (web/index.html not found)", file=sys.stderr)
        return 2
    if not (data / "facilities.geojson").exists():
        print(f"no map data in {data}: run `pull-berlin publish` first", file=sys.stderr)
        return 2
    server = make_server(Path("web"), data, port)
    print(f"map: http://127.0.0.1:{server.server_address[1]}/  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def _classifier(name: str, cache: Path, batch_size: int) -> TextClassifier:
    if name == "keywords":
        return KeywordClassifier()
    from pull_berlin.extraction.laya_classifier import LayaClassifier

    laya = LayaClassifier(batch_size=batch_size)
    cached = CachingClassifier(laya, cache / "judgements" / f"{laya.model_id}.jsonl", QUESTION_SET_V1.version)
    return cached if name == "laya-ungated" else LexicalGate(cached)


# --- publishing the catalog with human reviews -------------------------------------------------

CATALOG = Path("data/catalog/facilities.json")
REVIEWS = Path("data/reviews")
PUBLISHED = Path("data/published")


def _catalog_args(command: argparse.ArgumentParser) -> None:
    command.add_argument("--catalog", type=Path, default=CATALOG, help="catalog snapshot (JSON export)")
    command.add_argument("--reviews", type=Path, default=REVIEWS, help="folder of <reviewer>.jsonl files")


def _load_catalog(path: Path) -> list[Facility]:
    if not path.exists():
        raise SystemExit(f"no catalog snapshot at {path}; run from the project root")
    return read_snapshot(path.read_text(encoding="utf-8"))


def _publish(args: argparse.Namespace) -> int:
    try:
        reviews = ReviewStore(args.reviews).load()
    except ReviewFileError as error:
        print(f"bad review file: {error}", file=sys.stderr)
        return 1
    result = publish(_load_catalog(args.catalog), reviews)
    for path in write_outputs(result.facilities, args.out):
        print(f"wrote {path}")
    print(f"facilities={len(result.facilities)} reviews={len(reviews)} reviewed_facilities={result.reviewed}")
    for stray in result.unknown:
        print(f"warning: {stray.reviewer} reviewed {stray.facility_id}, which is not in the catalog")
    return 0


# --- human review ------------------------------------------------------------------------------


def _review_parser(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    review = commands.add_parser("review", help="check the catalog by hand (see skills/review-venues)")
    actions = review.add_subparsers(dest="action", required=True)

    def command(name: str, help_text: str, reviewer: bool = True) -> argparse.ArgumentParser:
        sub = actions.add_parser(name, help=help_text)
        _catalog_args(sub)
        sub.add_argument("--cache", type=Path, default=Path("data/cache"))
        if reviewer:
            sub.add_argument(
                "--reviewer",
                default=os.environ.get("PULL_BERLIN_REVIEWER"),
                help="your GitHub user name (or set PULL_BERLIN_REVIEWER)",
            )
        return sub

    next_cmd = command("next", "show the next facility to check, with what the model reads on its website")
    next_cmd.add_argument("--facility", help="check this facility instead: an id, or part of its name")
    next_cmd.add_argument(
        "--classifier",
        choices=("laya", "keywords", "none"),
        default="laya",
        help="who reads the website: Laya (default; `uv sync --extra laya`), the keyword baseline, or nobody",
    )
    next_cmd.add_argument("--offline", action="store_true", help="only read websites already in the cache")
    next_cmd.add_argument("--laya-batch-size", type=int, default=4)

    record = command("record", "save your answers for a facility to data/reviews/<you>.jsonl")
    record.add_argument("--facility", required=True, help="facility id, as shown by `review next`")
    for short in REVIEWED_CLAIMS:
        record.add_argument(f"--{short}", choices=[v.value for v in Verdict], default=Verdict.UNSURE.value)
    record.add_argument("--note", default="", help="optional: what you saw, in a sentence")

    skip = command("skip", "do not offer this facility to you again (kept locally, not shared)")
    skip.add_argument("--facility", required=True)

    command("summary", "what your reviews change on the map, as Markdown for a pull request")
    command("check", "validate every review file (used by CI)", reviewer=False)


def _review(args: argparse.Namespace) -> int:
    store = ReviewStore(args.reviews)
    try:
        reviews = store.load()
    except ReviewFileError as error:
        print(f"bad review file: {error}", file=sys.stderr)
        return 1
    if args.action == "check":
        return _review_check(args, reviews)
    if not args.reviewer:
        print("who is reviewing? pass --reviewer <your GitHub user name>", file=sys.stderr)
        return 2
    try:
        reviewer = valid_reviewer(args.reviewer)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    facilities = _load_catalog(args.catalog)
    state = args.cache / "review"
    pending = state / f"pending-{reviewer}.json"
    skipped = state / f"skipped-{reviewer}.txt"

    if args.action == "skip":
        state.mkdir(parents=True, exist_ok=True)
        with skipped.open("a", encoding="utf-8") as file:
            file.write(args.facility + "\n")
        print(f"skipped {args.facility}")
        return 0

    if args.action == "summary":
        mine = [r for r in reviews if r.reviewer == reviewer]
        others = [r for r in reviews if r.reviewer != reviewer]
        before = publish(facilities, others).facilities
        after = publish(facilities, reviews).facilities
        print(_summary_markdown(reviewer, len({r.facility_id for r in mine}), changes(before, after)))
        return 0

    reviewed, _ = with_reviews(facilities, reviews)
    if args.action == "next":
        if args.facility:
            matches = find(reviewed, args.facility)
            if len(matches) != 1:
                print(json.dumps({"matches": [{"facility": f.id, "name": f.name.display} for f in matches]}))
                return 0 if matches else 1
            chosen: Facility | None = matches[0]
        else:
            done = skipped.read_text(encoding="utf-8").split() if skipped.exists() else []
            chosen = choose_next(reviewed, reviews, skipped=done)
        if chosen is None:
            print(json.dumps({"done": True, "message": "nothing left to review"}))
            return 0
        classifier = _review_classifier(args) if chosen.websites else None
        fetcher = CachingFetcher(args.cache, None if args.offline else HttpFetcher())
        item = prepare(chosen, VenueSiteSource(), fetcher, classifier)
        state.mkdir(parents=True, exist_ok=True)
        pending.write_text(json.dumps(item.to_dict(), ensure_ascii=False), encoding="utf-8")
        print(json.dumps(item.to_dict(), ensure_ascii=False, indent=1))
        return 0

    # record
    by_id = {f.id: f for f in reviewed}
    if args.facility not in by_id:
        print(
            f"{args.facility} is not in the catalog; use the id that `review next` printed", file=sys.stderr
        )
        return 1
    saved = (
        ReviewItem.from_dict(json.loads(pending.read_text(encoding="utf-8"))) if pending.exists() else None
    )
    item = (
        saved
        if saved and saved.facility_id == args.facility
        else prepare(by_id[args.facility], None, None, None)
    )
    answers = {short: Verdict(getattr(args, short)) for short in REVIEWED_CLAIMS}
    try:
        review = item.review(reviewer, answers, date.today(), args.note.strip())
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    path = store.append(review)
    before = publish(facilities, reviews).facilities
    after = publish(facilities, [*reviews, review]).facilities
    old = next((v for v in before if v.id == args.facility), None)
    new = next((v for v in after if v.id == args.facility), None)
    print(f"saved to {path}")
    print(f"{review.facility_name}: {describe(old)} -> {describe(new)}")
    return 0


def _review_classifier(args: argparse.Namespace) -> TextClassifier | None:
    if args.classifier == "none":
        return None
    if args.classifier == "keywords":
        return KeywordClassifier()
    try:
        return _classifier("laya", args.cache, args.laya_batch_size)
    except ImportError:
        raise SystemExit(
            "Laya is not installed. Run `uv sync --extra laya` (first run downloads the model), "
            "or use `--classifier keywords`."
        ) from None


def _review_check(args: argparse.Namespace, reviews: list[Review]) -> int:
    result = publish(_load_catalog(args.catalog), reviews)
    for stray in result.unknown:
        print(f"warning: {stray.reviewer} reviewed {stray.facility_id}, which is not in the catalog")
    people = len({r.reviewer for r in reviews})
    print(f"ok: {len(reviews)} reviews by {people} people, {result.reviewed} facilities reviewed")
    return 0


def _summary_markdown(reviewer: str, count: int, found: list[Change]) -> str:
    lines = [
        f"Human review by @{reviewer}: {count} facilities checked, {len(found)} change on the map.",
        "",
    ]
    if found:
        lines += ["| facility | before | after |", "|---|---|---|"]
        lines += [f"| {c.name} (`{c.facility_id}`) | {c.before} | {c.after} |" for c in found]
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
