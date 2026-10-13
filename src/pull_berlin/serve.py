"""Serves the map on localhost the way GitHub Pages does: the page at `/`, its data at `/data/`.

The page comes from `web/`, the data from the publish output (`data/published/` by default), so
what you see locally is what the site will show.
"""

from __future__ import annotations

import functools
import os
import posixpath
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


class _Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args: object, data: Path, **kwargs: object) -> None:
        self._data = data
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]

    def translate_path(self, path: str) -> str:
        route = posixpath.normpath(unquote(urlsplit(path).path))
        if route == "/data" or route.startswith("/data/"):
            relative = route.removeprefix("/data").lstrip("/")
            if ".." in Path(relative).parts:
                return str(self._data / "__missing__")
            return str(self._data / relative)
        return super().translate_path(path)

    def guess_type(self, path: str | os.PathLike[str]) -> str:
        if str(path).endswith(".geojson"):
            return "application/geo+json"
        if str(path).endswith(".js"):
            return "text/javascript"  # module scripts need a JavaScript type on every platform
        return super().guess_type(path)

    def log_message(self, format: str, *args: object) -> None:
        pass


def make_server(web: Path, data: Path, port: int = 8000) -> ThreadingHTTPServer:
    handler = functools.partial(_Handler, directory=str(web), data=data.resolve())
    return ThreadingHTTPServer(("127.0.0.1", port), handler)
