from __future__ import annotations

import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from pull_berlin.sourcing.adapters import HttpFetcher
from pull_berlin.sourcing.domain import FetchRequest
from pull_berlin.sourcing.ports import FetchError

SEEN: list[tuple[str, str, str]] = []


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        SEEN.append((self.path, self.headers["User-Agent"], ""))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"<p>ok</p>")

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers["Content-Length"])).decode()
        SEEN.append((self.path, self.headers["User-Agent"], body))
        status = 429 if self.path == "/busy" else 200
        self.send_response(status)
        self.end_headers()
        self.wfile.write(b'{"elements": []}')

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def server() -> Iterator[str]:
    SEEN.clear()
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def test_post_sends_form_fields_url_encoded_and_identifies_the_client(server: str) -> None:
    document = HttpFetcher(min_interval_s=0).fetch(
        FetchRequest("osm", server + "/q", "POST", form=(("data", "[out:json];"),))
    )
    _path, user_agent, body = SEEN[0]
    assert document.content == '{"elements": []}'
    assert user_agent.startswith("pull-berlin/")
    assert body == "data=%5Bout%3Ajson%5D%3B"


def test_error_status_is_a_fetch_error_after_retries(server: str) -> None:
    with pytest.raises(FetchError, match="429"):
        HttpFetcher(min_interval_s=0, retries=1, backoff_s=0).fetch(
            FetchRequest("osm", server + "/busy", "POST", form=(("data", "q"),))
        )
    assert len(SEEN) == 2


def test_urls_with_umlauts_are_percent_encoded_not_a_crash(server: str) -> None:
    document = HttpFetcher(min_interval_s=0).fetch(FetchRequest("site", server + "/räume?saal=groß"))
    assert document.content == "<p>ok</p>"
    assert SEEN[-1][0] == "/r%C3%A4ume?saal=gro%C3%9F"


def test_a_malformed_url_is_a_fetch_error_not_a_crash() -> None:
    with pytest.raises(FetchError):
        HttpFetcher(min_interval_s=0, retries=0).fetch(FetchRequest("site", "https://exa mple.org:99999/"))
