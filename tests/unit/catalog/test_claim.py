from __future__ import annotations

import pytest

from pull_berlin.catalog.domain.claim import ClaimType, Proposition
from pull_berlin.catalog.domain.values import SpaceCategory

from .builders import evidence


class TestEvidence:
    def test_strength_above_one_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            evidence(strength=1.2)

    def test_negative_strength_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            evidence(strength=-0.1)

    def test_evidence_without_url_is_rejected_because_provenance_is_mandatory(self) -> None:
        with pytest.raises(ValueError):
            evidence(url="")


class TestProposition:
    def test_category_proposition_requires_a_category(self) -> None:
        with pytest.raises(ValueError):
            Proposition(ClaimType.FALLS_UNDER_CATEGORY)

    def test_yes_no_proposition_must_not_carry_a_category(self) -> None:
        with pytest.raises(ValueError):
            Proposition(ClaimType.IS_HIREABLE_FOR_PRIVATE_EVENTS, SpaceCategory.CLUB)

    def test_propositions_with_same_content_are_equal(self) -> None:
        a = Proposition(ClaimType.FALLS_UNDER_CATEGORY, SpaceCategory.BAR)
        b = Proposition(ClaimType.FALLS_UNDER_CATEGORY, SpaceCategory.BAR)
        assert a == b
