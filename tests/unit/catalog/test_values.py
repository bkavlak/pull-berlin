from __future__ import annotations

import pytest

from pull_berlin.catalog.domain.values import GeoPoint, NotInBerlinError, SpaceCategory, SpaceName, TimeWindow

ALEXANDERPLATZ = GeoPoint(lat=52.5219, lon=13.4132)


class TestGeoPoint:
    def test_rejects_latitude_outside_the_globe(self) -> None:
        with pytest.raises(ValueError):
            GeoPoint(lat=91.0, lon=13.4)

    def test_rejects_longitude_outside_the_globe(self) -> None:
        with pytest.raises(ValueError):
            GeoPoint(lat=52.5, lon=181.0)

    def test_distance_between_identical_points_is_zero(self) -> None:
        assert ALEXANDERPLATZ.distance_m(ALEXANDERPLATZ) == 0.0

    def test_distance_alexanderplatz_to_brandenburg_gate_is_about_two_and_a_half_km(self) -> None:
        brandenburg_gate = GeoPoint(lat=52.5163, lon=13.3777)
        assert 2_300 < ALEXANDERPLATZ.distance_m(brandenburg_gate) < 2_600

    def test_point_in_berlin_passes_the_berlin_check(self) -> None:
        assert ALEXANDERPLATZ.require_in_berlin() == ALEXANDERPLATZ

    def test_point_in_potsdam_is_not_in_berlin(self) -> None:
        with pytest.raises(NotInBerlinError):
            GeoPoint(lat=52.3906, lon=13.0645).require_in_berlin()


class TestSpaceName:
    def test_blank_name_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            SpaceName("   ")

    def test_display_keeps_original_spelling_but_trims(self) -> None:
        assert SpaceName("  Club der Visionäre ").display == "Club der Visionäre"

    def test_normalized_folds_case_umlauts_and_punctuation(self) -> None:
        assert SpaceName("Café Größenwahn!").normalized == "cafe groessenwahn"

    def test_normalized_drops_generic_venue_words(self) -> None:
        assert SpaceName("Club Tresor Berlin").normalized == SpaceName("Tresor").normalized

    def test_similarity_of_same_name_with_different_spelling_is_high(self) -> None:
        assert SpaceName("SO36").similarity(SpaceName("SO 36")) > 0.9

    def test_similarity_of_unrelated_names_is_low(self) -> None:
        assert SpaceName("Berghain").similarity(SpaceName("Kulturbrauerei")) < 0.5


class TestOntologyTerms:
    def test_every_time_window_names_its_ontology_term(self) -> None:
        assert all(window.ontology_term.startswith("https://w3id.org/pull-berlin/") for window in TimeWindow)

    def test_every_space_category_names_its_ontology_term(self) -> None:
        assert all(cat.ontology_term.startswith("https://w3id.org/pull-berlin/") for cat in SpaceCategory)
