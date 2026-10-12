"""A facility's own website: the most authoritative place to learn whether it can be hired.

Visits the homepage and a few same-site pages whose link looks relevant ("Location mieten",
"Private Events", "Programm"), honouring robots.txt. Produces Passages; deciding what they say
is the extraction context's job (Laya), not this adapter's.
"""

from __future__ import annotations

import re
import urllib.robotparser
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urldefrag, urljoin, urlsplit

from pull_berlin.catalog.domain.facility import Facility
from pull_berlin.catalog.domain.observation import Observation, Passage
from pull_berlin.shared_kernel import SourceKind
from pull_berlin.sourcing.domain import FetchRequest, Source
from pull_berlin.sourcing.ports import Fetcher, FetchError

ROBOTS_AGENT = "pull-berlin"
_RELEVANT = re.compile(
    r"miet|location|event|veranstalt|feier|party|hochzeit|privat|buch|r[aä]um|saal|halle|konzert|programm|"
    r"club|kapazit|personen|g[aä]ste|rent|hire|venue|booking|spaces?\b",
    re.IGNORECASE,
)
_SKIPPED_TAGS = {"script", "style", "noscript", "svg", "template", "iframe", "head"}
_BLOCK_TAGS = {
    "p",
    "div",
    "li",
    "br",
    "tr",
    "section",
    "article",
    "header",
    "footer",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "nav",
}
_FILE_SUFFIX = re.compile(r"\.(pdf|jpe?g|png|gif|webp|svg|zip|docx?|xlsx?|mp[34])$", re.IGNORECASE)
_MIN_PASSAGE_CHARS = 40
_MIN_PROSE_WORDS = 6  # shorter lines are menus, buttons and labels, not statements
_TIMEOUT_S = 20.0


@dataclass(frozen=True)
class PageText:
    title: str
    text: str
    links: tuple[tuple[str, str], ...]


class _Reader(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self._base = base_url
        self._skip_depth = 0
        self._in_title = False
        self._title: list[str] = []
        self._chunks: list[str] = []
        self._link: tuple[str, list[str]] | None = None
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self._in_title = True
        elif tag in _SKIPPED_TAGS:
            self._skip_depth += 1
        if tag in _BLOCK_TAGS:
            self._chunks.append("\n")
        if tag == "a":
            href = dict(attrs).get("href")
            self._link = (urljoin(self._base, href), []) if href else None

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag in _SKIPPED_TAGS and self._skip_depth:
            self._skip_depth -= 1
        if tag in _BLOCK_TAGS:
            self._chunks.append("\n")
        if tag == "a" and self._link is not None:
            url, words = self._link
            self.links.append((url, " ".join(" ".join(words).split())))
            self._link = None

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title.append(data)
        elif not self._skip_depth:
            data = data.replace("\n", " ")  # in HTML only block elements break lines
            self._chunks.append(data)
            if self._link is not None:
                self._link[1].append(data)

    def page(self) -> PageText:
        lines = (" ".join(line.split()) for line in "".join(self._chunks).split("\n"))
        return PageText(
            title=" ".join("".join(self._title).split()),
            text="\n".join(line for line in lines if line),
            links=tuple(self.links),
        )


def read_html(html: str, url: str) -> PageText:
    reader = _Reader(url)
    reader.feed(html)
    reader.close()
    return reader.page()


def homepage_url(website: str) -> str:
    website = website.strip()
    if not re.match(r"^https?://", website, re.IGNORECASE):
        website = "https://" + website
    parts = urlsplit(website)
    return website if parts.path else website + "/"


def candidate_links(page: PageText, homepage: str, limit: int) -> list[str]:
    """Same-site HTML pages whose URL or anchor text looks relevant, most relevant first."""
    home_host = _site(homepage)
    scored: dict[str, int] = {}
    for raw_url, anchor in page.links:
        url = urldefrag(raw_url).url
        parts = urlsplit(url)
        if (
            parts.scheme not in ("http", "https")
            or _site(url) != home_host
            or _FILE_SUFFIX.search(parts.path)
        ):
            continue
        if url.rstrip("/") == homepage.rstrip("/"):
            continue
        score = len(_RELEVANT.findall(parts.path)) + len(_RELEVANT.findall(anchor))
        if score:
            scored[url] = max(score, scored.get(url, 0))
    return sorted(scored, key=lambda u: (-scored[u], u))[:limit]


def passages(text: str, url: str, max_chars: int, limit: int) -> list[Passage]:
    """Packs prose lines into passages of <= `max_chars`; keeps the `limit` most relevant, in page order."""
    chunks: list[str] = []
    current = ""
    prose = (line for line in text.split("\n") if len(line.split()) >= _MIN_PROSE_WORDS)
    for paragraph in (p for line in prose for p in _split_long(line, max_chars)):
        if current and len(current) + 1 + len(paragraph) > max_chars:
            chunks.append(current)
            current = paragraph
        else:
            current = f"{current} {paragraph}".strip()
    if current:
        chunks.append(current)

    usable = [(i, c) for i, c in enumerate(chunks) if len(c) >= _MIN_PASSAGE_CHARS]
    best = sorted(usable, key=lambda item: (-len(_RELEVANT.findall(item[1])), item[0]))[:limit]
    return [Passage(text=chunk, url=url) for _, chunk in sorted(best)]


def _split_long(paragraph: str, max_chars: int) -> list[str]:
    pieces: list[str] = []
    while len(paragraph) > max_chars:
        cut = paragraph.rfind(" ", 0, max_chars)
        cut = cut if cut > 0 else max_chars
        pieces.append(paragraph[:cut])
        paragraph = paragraph[cut:].strip()
    return [*pieces, paragraph] if paragraph else pieces


def _site(url: str) -> str:
    host = urlsplit(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


class VenueSiteSource:
    def __init__(self, max_subpages: int = 3, passages_per_page: int = 3, passage_chars: int = 1500) -> None:
        self._source = Source(id="site", kind=SourceKind.VENUE_OWN_SITE, name="Venue websites")
        self._max_subpages = max_subpages
        self._passages_per_page = passages_per_page
        self._passage_chars = passage_chars

    @property
    def source(self) -> Source:
        return self._source

    def observe(self, facility: Facility, fetcher: Fetcher) -> Observation | None:
        if not facility.websites:
            return None
        home = homepage_url(sorted(facility.websites)[0])
        robots = self._robots(home, fetcher)
        if not robots.can_fetch(ROBOTS_AGENT, home):
            return None
        home_page = self._read(home, fetcher)
        if home_page is None:
            return None

        found = self._passages(home_page, home)
        for url in candidate_links(home_page, home, self._max_subpages):
            if robots.can_fetch(ROBOTS_AGENT, url) and (page := self._read(url, fetcher)) is not None:
                found += self._passages(page, url)

        return Observation(
            source_id=self._source.id,
            source_kind=self._source.kind,
            local_id=urlsplit(home).netloc.lower(),
            url=home,
            name=facility.name,
            location=facility.location,
            website=home,
            passages=tuple(found),
        )

    def _passages(self, page: PageText, url: str) -> list[Passage]:
        return passages(page.text, url, self._passage_chars, self._passages_per_page)

    def _read(self, url: str, fetcher: Fetcher) -> PageText | None:
        try:
            return read_html(fetcher.fetch(self._request(url)).content, url)
        except FetchError:
            return None

    def _robots(self, home: str, fetcher: Fetcher) -> urllib.robotparser.RobotFileParser:
        parser = urllib.robotparser.RobotFileParser()
        parts = urlsplit(home)
        try:
            content = fetcher.fetch(self._request(f"{parts.scheme}://{parts.netloc}/robots.txt")).content
        except FetchError:
            content = ""  # no robots.txt: everything allowed
        parser.parse(content.splitlines())
        return parser

    def _request(self, url: str) -> FetchRequest:
        return FetchRequest(
            source_id=self._source.id, url=url, timeout_s=_TIMEOUT_S, retries=1, remember_failure=True
        )
