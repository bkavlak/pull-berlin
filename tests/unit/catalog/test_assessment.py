from __future__ import annotations

import pytest

from pull_berlin.catalog.domain.assessment import AssessmentPolicy
from pull_berlin.catalog.domain.claim import ClaimType, Proposition, Stance
from pull_berlin.catalog.domain.offering import OfferingKind
from pull_berlin.catalog.domain.values import SpaceCategory, TimeWindow
from pull_berlin.shared_kernel import SourceKind

from .builders import statement

HIREABLE = Proposition(ClaimType.IS_HIREABLE_FOR_PRIVATE_EVENTS)
POLICY = AssessmentPolicy(
    priors={SourceKind.OPEN_GEODATA: 0.8, SourceKind.MAPS_AND_REVIEWS: 0.6}, threshold=0.6
)


class TestConfidence:
    def test_single_explicit_statement_gets_the_source_prior(self) -> None:
        result = POLICY.assess([statement(ClaimType.IS_HIREABLE_FOR_PRIVATE_EVENTS)])
        assert result.confidence(HIREABLE) == pytest.approx(0.8)

    def test_weak_evidence_scales_the_prior_down(self) -> None:
        result = POLICY.assess([statement(ClaimType.IS_HIREABLE_FOR_PRIVATE_EVENTS, strength=0.5)])
        assert result.confidence(HIREABLE) == pytest.approx(0.4)

    def test_independent_sources_reinforce_each_other(self) -> None:
        result = POLICY.assess(
            [
                statement(ClaimType.IS_HIREABLE_FOR_PRIVATE_EVENTS),
                statement(
                    ClaimType.IS_HIREABLE_FOR_PRIVATE_EVENTS,
                    source_id="gmaps",
                    kind=SourceKind.MAPS_AND_REVIEWS,
                ),
            ]
        )
        assert result.confidence(HIREABLE) == pytest.approx(1 - 0.2 * 0.4)

    def test_repeated_statements_from_one_source_count_once(self) -> None:
        once = POLICY.assess([statement(ClaimType.IS_HIREABLE_FOR_PRIVATE_EVENTS)])
        twice = POLICY.assess(
            [statement(ClaimType.IS_HIREABLE_FOR_PRIVATE_EVENTS, url=u) for u in ("a", "b")]
        )
        assert twice.confidence(HIREABLE) == once.confidence(HIREABLE)

    def test_opposing_evidence_lowers_confidence(self) -> None:
        result = POLICY.assess(
            [
                statement(ClaimType.IS_HIREABLE_FOR_PRIVATE_EVENTS),
                statement(
                    ClaimType.IS_HIREABLE_FOR_PRIVATE_EVENTS,
                    source_id="gmaps",
                    kind=SourceKind.MAPS_AND_REVIEWS,
                    stance=Stance.OPPOSES,
                ),
            ]
        )
        assert result.confidence(HIREABLE) == pytest.approx(0.8 * (1 - 0.6))

    def test_proposition_without_evidence_has_zero_confidence(self) -> None:
        assert POLICY.assess([]).confidence(HIREABLE) == 0.0

    def test_unknown_source_kind_falls_back_to_the_default_prior(self) -> None:
        result = POLICY.assess([statement(ClaimType.IS_HIREABLE_FOR_PRIVATE_EVENTS, kind=SourceKind.SOCIAL)])
        assert result.confidence(HIREABLE) == pytest.approx(POLICY.default_prior)

    def test_every_claim_keeps_its_evidence(self) -> None:
        result = POLICY.assess(
            [statement(ClaimType.IS_HIREABLE_FOR_PRIVATE_EVENTS, excerpt="amenity=events_venue")]
        )
        assert [e.excerpt for e in result.claims[0].evidence] == ["amenity=events_venue"]


class TestOfferings:
    def test_confident_hireability_yields_an_event_hire_offering(self) -> None:
        result = POLICY.assess([statement(ClaimType.IS_HIREABLE_FOR_PRIVATE_EVENTS)])
        assert [o.kind for o in result.offerings] == [OfferingKind.EVENT_HIRE]

    def test_hireability_below_threshold_yields_no_offering(self) -> None:
        result = POLICY.assess([statement(ClaimType.IS_HIREABLE_FOR_PRIVATE_EVENTS, strength=0.3)])
        assert result.offerings == ()

    def test_hosting_evening_events_yields_hosting_offering_in_the_evening_window(self) -> None:
        result = POLICY.assess([statement(ClaimType.HOSTS_EVENING_EVENTS)])
        (offering,) = result.offerings
        assert offering.kind is OfferingKind.EVENT_HOSTING
        assert offering.windows == frozenset({TimeWindow.EVENING})

    def test_operating_past_midnight_adds_the_night_window(self) -> None:
        result = POLICY.assess(
            [statement(ClaimType.HOSTS_EVENING_EVENTS), statement(ClaimType.OPERATES_PAST_MIDNIGHT)]
        )
        assert result.offerings[0].windows == frozenset({TimeWindow.EVENING, TimeWindow.NIGHT})

    def test_hire_offering_without_known_hours_has_no_windows(self) -> None:
        result = POLICY.assess([statement(ClaimType.IS_HIREABLE_FOR_PRIVATE_EVENTS)])
        assert result.offerings[0].windows == frozenset()

    def test_offering_confidence_is_the_confidence_of_its_claim(self) -> None:
        result = POLICY.assess([statement(ClaimType.IS_HIREABLE_FOR_PRIVATE_EVENTS, strength=0.9)])
        assert result.offerings[0].confidence == pytest.approx(0.72)

    def test_offering_kinds_name_their_ontology_roles(self) -> None:
        assert OfferingKind.EVENT_HIRE.ontology_term.endswith("/EventHireRole")
        assert OfferingKind.EVENT_HOSTING.ontology_term.endswith("/EventHostingRole")


class TestCategories:
    def test_categories_are_graded_and_ordered_by_degree(self) -> None:
        result = POLICY.assess(
            [
                statement(ClaimType.FALLS_UNDER_CATEGORY, SpaceCategory.BAR, strength=0.5),
                statement(ClaimType.FALLS_UNDER_CATEGORY, SpaceCategory.CLUB),
            ]
        )
        assert [c for c, _ in result.categories] == [SpaceCategory.CLUB, SpaceCategory.BAR]

    def test_primary_category_is_none_when_nothing_is_known(self) -> None:
        assert POLICY.assess([]).primary_category is None


class TestPolicyValidation:
    def test_threshold_outside_unit_interval_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            AssessmentPolicy(priors={}, threshold=1.5)

    def test_prior_outside_unit_interval_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            AssessmentPolicy(priors={SourceKind.OPEN_GEODATA: 2.0})
