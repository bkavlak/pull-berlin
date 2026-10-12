"""Command line: `pull-berlin pull` runs every source and writes the exports."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from pull_berlin.application.pull import pull
from pull_berlin.extraction.caching_classifier import CachingClassifier
from pull_berlin.extraction.gate import LexicalGate
from pull_berlin.extraction.keyword_classifier import KeywordClassifier
from pull_berlin.extraction.ports import TextClassifier
from pull_berlin.extraction.questions import QUESTION_SET_V1
from pull_berlin.publishing.renderers import write_outputs
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
    pull_cmd.add_argument("--laya-batch-size", type=int, default=4, help="texts per Laya forward pass")
    serve_cmd = commands.add_parser("serve", help="open the map: serve web/ and data/out/ on localhost")
    serve_cmd.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    if args.command == "serve":
        return _serve(args.port)

    fetcher = CachingFetcher(args.cache, None if args.offline else HttpFetcher())
    try:
        result = pull(
            available_sources(),
            fetcher,
            include_all=args.all,
            enrichers=[VenueSiteSource()] if args.sites else [],
            classifier=_classifier(args.classifier, args.cache, args.laya_batch_size) if args.sites else None,
            enrich_limit=args.site_limit,
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


def _serve(port: int) -> int:
    from pull_berlin.serve import make_server

    if not Path("web/index.html").exists():
        print("run this from the project root (web/index.html not found)", file=sys.stderr)
        return 2
    server = make_server(Path.cwd(), port)
    print(f"map: http://127.0.0.1:{server.server_address[1]}/web/  (Ctrl+C to stop)")
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


if __name__ == "__main__":
    sys.exit(main())
