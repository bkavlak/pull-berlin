"""Fetcher adapters: polite HTTP, and a disk cache that doubles as the recorder for test fixtures."""

from __future__ import annotations

import http.client
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from pull_berlin.sourcing.domain import FetchRequest, RawDocument
from pull_berlin.sourcing.ports import Fetcher, FetchError

USER_AGENT = "pull-berlin/0.1 (+https://github.com/bkavlak/pull-berlin)"
_RETRYABLE = {429, 500, 502, 503, 504}


class HttpFetcher:
    """urllib-based fetcher: identifies itself, waits between requests to the same host, retries
    rate limits and server errors with linear backoff."""

    def __init__(
        # Overpass answers 504 in bursts when busy; frequent short retries recover faster than long waits.
        self,
        min_interval_s: float = 2.0,
        retries: int = 8,
        backoff_s: float = 5.0,
        timeout_s: float = 240.0,
    ) -> None:
        self._min_interval_s = min_interval_s
        self._retries = retries
        self._backoff_s = backoff_s
        self._timeout_s = timeout_s
        self._last_request_at: dict[str, float] = {}
        self._lock = threading.Lock()

    def fetch(self, request: FetchRequest) -> RawDocument:
        last_error = ""
        retries = self._retries if request.retries is None else request.retries
        timeout = self._timeout_s if request.timeout_s is None else request.timeout_s
        for attempt in range(retries + 1):
            if attempt:
                time.sleep(self._backoff_s * attempt)
            self._wait_for_turn(request.url)
            try:
                with urllib.request.urlopen(self._prepare(request), timeout=timeout) as response:
                    charset = response.headers.get_content_charset() or "utf-8"
                    content = response.read().decode(charset, errors="replace")
                return RawDocument(request.source_id, request.url, content, datetime.now(timezone.utc))
            except urllib.error.HTTPError as error:
                last_error = f"HTTP {error.code} from {request.url}"
                if error.code not in _RETRYABLE:
                    break
            except (urllib.error.URLError, TimeoutError, ConnectionError, LookupError) as error:
                last_error = f"{error} for {request.url}"
            except (http.client.HTTPException, ValueError, OSError) as error:
                # Malformed URLs, broken servers, TLS oddities: this source is unreachable, not a bug in us.
                last_error = f"{type(error).__name__}: {error} for {request.url}"
                break
        raise FetchError(last_error)

    def _prepare(self, request: FetchRequest) -> urllib.request.Request:
        data = urllib.parse.urlencode(request.form).encode() if request.form else None
        headers = {"User-Agent": USER_AGENT, "Accept": "*/*", **dict(request.headers)}
        return urllib.request.Request(
            _ascii_url(request.url), data=data, headers=headers, method=request.method
        )

    def _wait_for_turn(self, url: str) -> None:
        """Reserves this host's next slot under a lock, then sleeps outside it (other hosts go on)."""
        host = urllib.parse.urlsplit(url).netloc
        with self._lock:
            now = time.monotonic()
            slot = max(now, self._last_request_at.get(host, float("-inf")) + self._min_interval_s)
            self._last_request_at[host] = slot
        if slot > now:
            time.sleep(slot - now)


def _ascii_url(url: str) -> str:
    """Percent-encodes non-ASCII characters (IRI -> URI); existing escapes and URL syntax stay."""
    return urllib.parse.quote(url, safe=":/?#[]@!$&'()*+,;=%~")


class CachingFetcher:
    """Serves recorded documents from `cache_dir/<source>/<request fingerprint>.json`.

    With an inner fetcher, misses are fetched and recorded. Without one (offline), a miss is a
    FetchError — which is how e2e tests guarantee they never touch the internet.
    """

    def __init__(self, cache_dir: Path, inner: Fetcher | None, retry_failed: bool = False) -> None:
        self._cache_dir = cache_dir
        self._inner = inner
        self._retry_failed = retry_failed

    def fetch(self, request: FetchRequest) -> RawDocument:
        path = self._cache_dir / request.source_id / f"{request.fingerprint}.json"
        if path.exists():
            record = json.loads(path.read_text(encoding="utf-8"))
            failed_before = "error" in record
            if failed_before and (self._retry_failed is False or self._inner is None):
                raise FetchError(
                    f"failed earlier ({record['error']}); rerun with --retry-failed to try again"
                )
        if path.exists() and not failed_before:
            return RawDocument(
                request.source_id,
                record["url"],
                record["content"],
                datetime.fromisoformat(record["fetched_at"]),
            )
        if self._inner is None:
            raise FetchError(f"offline and no recording for {request.url} ({path.name})")

        try:
            document = self._inner.fetch(request)
        except FetchError as error:
            if request.remember_failure:
                path.parent.mkdir(parents=True, exist_ok=True)
                failure = {
                    "url": request.url,
                    "failed_at": datetime.now(timezone.utc).isoformat(),
                    "error": str(error),
                }
                path.write_text(json.dumps(failure, ensure_ascii=False), encoding="utf-8")
            raise
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "url": document.url,
            "fetched_at": document.fetched_at.isoformat(),
            "request": {"method": request.method, "form": request.form},
            "content": document.content,
        }
        path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        return document
