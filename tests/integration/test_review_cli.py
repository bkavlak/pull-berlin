"""The contributor loop on disk: show a facility, record answers, publish the map data."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pull_berlin.application.publish import publish
from pull_berlin.catalog.domain.claim import ClaimType
from pull_berlin.cli import main
from pull_berlin.publishing.renderers import render_json

from ..unit.catalog.builders import facility, statement

HALL = facility(
    local_id="node/7",
    name="Festsaal Kreuzberg",
    website="https://festsaal.example",
    statements=(
        statement(ClaimType.IS_HIREABLE_FOR_PRIVATE_EVENTS),
        statement(ClaimType.OPERATES_IN_EVENING),
    ),
)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "catalog.json").write_text(render_json(publish([HALL], []).facilities), encoding="utf-8")
    return tmp_path


def run(repo: Path, *args: str) -> int:
    paths = ["--catalog", str(repo / "catalog.json"), "--reviews", str(repo / "reviews")]
    if args[0] == "review":
        paths += ["--cache", str(repo / "cache")]
    return main([*args, *paths])


def test_a_recorded_no_lands_in_the_reviewers_file_and_takes_the_facility_off_the_map(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(repo, "review", "next", "--reviewer", "ada", "--classifier", "none") == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["facility"] == "osm:node/7"

    assert (
        run(repo, "review", "record", "--reviewer", "ada", "--facility", "osm:node/7", "--hireable", "no")
        == 0
    )
    assert "-> not on the map" in capsys.readouterr().out
    (line,) = (repo / "reviews" / "ada.jsonl").read_text().splitlines()
    assert json.loads(line)["verdicts"] == {"hireable": "no", "hosts": "unsure", "late": "unsure"}

    assert run(repo, "publish", "--out", str(repo / "out")) == 0
    published = json.loads((repo / "out" / "facilities.geojson").read_text())
    assert published["features"] == []


def test_the_queue_ends_once_everything_is_reviewed(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run(repo, "review", "record", "--reviewer", "ada", "--facility", "osm:node/7", "--hireable", "yes")
    capsys.readouterr()
    run(repo, "review", "next", "--reviewer", "ada", "--classifier", "none")
    assert json.loads(capsys.readouterr().out)["done"] is True


def test_summary_lists_what_my_reviews_change(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run(repo, "review", "record", "--reviewer", "ada", "--facility", "osm:node/7", "--hireable", "no")
    capsys.readouterr()
    run(repo, "review", "summary", "--reviewer", "ada")
    summary = capsys.readouterr().out
    assert "@ada: 1 facilities checked, 1 change" in summary
    assert "| Festsaal Kreuzberg (`osm:node/7`) | event_hire 0.80 (evening) | not on the map |" in summary


def test_check_rejects_a_review_filed_under_someone_elses_name(repo: Path) -> None:
    (repo / "reviews").mkdir()
    record = {
        "facility": "osm:node/7",
        "reviewer": "mallory",
        "reviewed_on": "2026-10-13",
        "verdicts": {"hosts": "no"},
    }
    (repo / "reviews" / "ada.jsonl").write_text(json.dumps(record) + "\n")
    assert run(repo, "review", "check") == 1
