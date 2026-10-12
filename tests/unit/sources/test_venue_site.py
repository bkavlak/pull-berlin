from __future__ import annotations

from pull_berlin.catalog.domain.claim import ClaimType, Proposition
from pull_berlin.catalog.domain.facility import ExternalRef
from pull_berlin.shared_kernel import SourceKind
from pull_berlin.sources.venue_site import (
    VenueSiteSource,
    candidate_links,
    homepage_url,
    passages,
    read_html,
)

from ...fakes import FakeFetcher
from ..catalog.builders import facility

HOME = "https://www.example-venue.de/"
HOME_HTML = """<html><head><title>Example Venue</title><style>.x{}</style></head><body>
<nav><a href="/">Home</a><a href="/location-mieten">Location mieten</a><a href="/kontakt">Kontakt</a>
<a href="https://www.instagram.com/examplevenue">Instagram</a><a href="/presse.pdf">Presse</a>
<a href="/programm">Programm</a><a href="mailto:info@example-venue.de">Mail</a></nav>
<script>var tracking = "mieten";</script>
<p>Willkommen im Example Venue in Friedrichshain.</p></body></html>"""
RENT_HTML = """<html><body><h1>Location mieten</h1>
<p>Unser Saal mit 300 Plätzen kann für Hochzeiten, Firmenfeiern und private Partys gemietet werden.
Anfragen bitte per Mail.</p></body></html>"""


class TestReadHtml:
    def test_title_and_visible_text_without_scripts_or_styles(self) -> None:
        page = read_html(HOME_HTML, HOME)
        assert page.title == "Example Venue"
        assert "Willkommen im Example Venue" in page.text
        assert "tracking" not in page.text

    def test_links_are_absolute_with_their_anchor_text(self) -> None:
        page = read_html(HOME_HTML, HOME)
        assert ("https://www.example-venue.de/location-mieten", "Location mieten") in page.links


class TestCandidateLinks:
    def test_rental_and_event_pages_on_the_same_site_are_followed(self) -> None:
        links = candidate_links(read_html(HOME_HTML, HOME), HOME, limit=3)
        assert links[0] == "https://www.example-venue.de/location-mieten"
        assert "https://www.example-venue.de/programm" in links

    def test_other_sites_files_and_mail_links_are_never_followed(self) -> None:
        links = candidate_links(read_html(HOME_HTML, HOME), HOME, limit=10)
        assert not any("instagram" in u or u.endswith(".pdf") or u.startswith("mailto") for u in links)

    def test_pages_without_any_signal_are_not_followed(self) -> None:
        assert "https://www.example-venue.de/kontakt" not in candidate_links(
            read_html(HOME_HTML, HOME), HOME, 10
        )


class TestPassages:
    def test_text_is_cut_into_bounded_passages_that_keep_the_page_url(self) -> None:
        text = "\n".join(f"Absatz {i}: " + "Wir vermieten Räume für Feiern. " * 10 for i in range(20))
        result = passages(text, "https://x.example/p", max_chars=600, limit=3)
        assert len(result) == 3
        assert all(len(p.text) <= 600 and p.url == "https://x.example/p" for p in result)

    def test_relevant_paragraphs_are_preferred_over_boilerplate(self) -> None:
        text = (
            "Cookie-Einstellungen und Datenschutz " * 5
            + "\n"
            + "Die Halle kann für private Feiern gemietet werden. " * 3
        )
        (passage,) = passages(text, "https://x.example", max_chars=200, limit=1)
        assert "gemietet" in passage.text

    def test_fragments_too_short_to_judge_are_dropped(self) -> None:
        assert passages("Menü\nHome\nKontakt", "https://x.example", max_chars=600, limit=3) == []


class TestHomepageUrl:
    def test_scheme_is_added_and_path_defaults_to_root(self) -> None:
        assert homepage_url("www.example.de") == "https://www.example.de/"

    def test_existing_url_is_kept(self) -> None:
        assert homepage_url("http://example.de/de/start") == "http://example.de/de/start"


class TestObserve:
    def test_homepage_and_rental_page_become_passages_of_one_observation(self) -> None:
        fetcher = FakeFetcher(
            {HOME: HOME_HTML, HOME + "location-mieten": RENT_HTML, HOME + "programm": RENT_HTML}
        )
        venue = facility(website="www.example-venue.de")
        obs = VenueSiteSource().observe(venue, fetcher)
        assert obs is not None
        assert obs.source_kind is SourceKind.VENUE_OWN_SITE
        assert (obs.source_id, obs.local_id) == ("site", "www.example-venue.de")
        assert any("gemietet" in p.text and p.url.endswith("location-mieten") for p in obs.passages)

    def test_observation_is_about_the_facility_it_was_crawled_for(self) -> None:
        fetcher = FakeFetcher({HOME: HOME_HTML})
        venue = facility(website=HOME)
        obs = VenueSiteSource().observe(venue, fetcher)
        assert obs is not None and (obs.name, obs.location) == (venue.name, venue.location)

    def test_robots_txt_disallowing_us_means_no_visit(self) -> None:
        fetcher = FakeFetcher({HOME + "robots.txt": "User-agent: *\nDisallow: /", HOME: HOME_HTML})
        assert VenueSiteSource().observe(facility(website=HOME), fetcher) is None
        assert [r.url for r in fetcher.requests] == [HOME + "robots.txt"]

    def test_unreachable_homepage_means_no_observation(self) -> None:
        assert VenueSiteSource().observe(facility(website=HOME), FakeFetcher({})) is None

    def test_broken_subpage_does_not_lose_the_homepage(self) -> None:
        obs = VenueSiteSource().observe(facility(website=HOME), FakeFetcher({HOME: HOME_HTML}))
        assert obs is not None and obs.passages

    def test_facility_without_website_is_not_visited(self) -> None:
        fetcher = FakeFetcher({})
        assert VenueSiteSource().observe(facility(), fetcher) is None
        assert fetcher.requests == []

    def test_site_requests_are_short_and_not_retried_much(self) -> None:
        fetcher = FakeFetcher({HOME: HOME_HTML})
        VenueSiteSource().observe(facility(website=HOME), fetcher)
        assert all(r.timeout_s is not None and r.timeout_s <= 30 for r in fetcher.requests)


class TestAbsorb:
    def test_facility_absorbs_an_enrichment_observation_without_changing_identity(self) -> None:
        venue = facility(local_id="node/1", website=HOME)
        fetcher = FakeFetcher({HOME: HOME_HTML})
        obs = VenueSiteSource().observe(venue, fetcher)
        assert obs is not None
        enriched = venue.absorb(obs.with_statements(()))
        assert enriched.id == venue.id
        assert ExternalRef("site", "www.example-venue.de") in enriched.refs

    def test_absorbed_statements_join_the_facilitys_evidence(self) -> None:
        from ..catalog.builders import observation, statement

        extra = observation(
            source_id="site",
            local_id="x.de",
            statements=(statement(ClaimType.IS_HIREABLE_FOR_PRIVATE_EVENTS),),
        )
        enriched = facility().absorb(extra)
        assert Proposition(ClaimType.IS_HIREABLE_FOR_PRIVATE_EVENTS) in {
            s.proposition for s in enriched.statements
        }


class TestProseOnly:
    def test_navigation_menus_do_not_become_passages(self) -> None:
        menu = "\n".join(["Home", "Über uns", "Location mieten", "Kontakt", "Impressum"] * 10)
        assert passages(menu, "https://x.example", max_chars=600, limit=3) == []

    def test_sentences_survive_between_menu_lines(self) -> None:
        text = "Home\nKontakt\nUnser Saal kann für private Feiern und Hochzeiten gemietet werden.\nImpressum"
        (passage,) = passages(text, "https://x.example", max_chars=600, limit=3)
        assert passage.text == "Unser Saal kann für private Feiern und Hochzeiten gemietet werden."
