"""Serves the map (web/) and the exports (data/out/) from the project root, on localhost only."""

from __future__ import annotations

import functools
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class _Handler(SimpleHTTPRequestHandler):
    def guess_type(self, path: str | os.PathLike[str]) -> str:
        if str(path).endswith(".geojson"):
            return "application/geo+json"
        if str(path).endswith(".js"):
            return "text/javascript"  # module scripts need a JavaScript type on every platform
        return super().guess_type(path)

    def log_message(self, format: str, *args: object) -> None:
        pass


def make_server(root: Path, port: int = 8000) -> ThreadingHTTPServer:
    handler = functools.partial(_Handler, directory=str(root))
    return ThreadingHTTPServer(("127.0.0.1", port), handler)
