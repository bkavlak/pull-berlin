"""Command line: `pull-berlin pull` runs every source and writes the exports."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from pull_berlin.application.pull import pull
from pull_berlin.publishing.renderers import write_outputs
from pull_berlin.sources.osm_overpass import OsmOverpassSource
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
    args = parser.parse_args(argv)

    fetcher = CachingFetcher(args.cache, None if args.offline else HttpFetcher())
    try:
        result = pull(available_sources(), fetcher, include_all=args.all)
    except FetchError as error:
        print(f"fetch failed: {error}", file=sys.stderr)
        return 2

    written = write_outputs(result.facilities, args.out)
    report = result.report
    print(
        f"observations={report.observations} {report.observations_per_source} "
        f"outside_berlin={report.outside_berlin} facilities={report.facilities} in_scope={report.in_scope}"
    )
    for path in written:
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
