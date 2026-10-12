from __future__ import annotations

import threading
import urllib.request
from pathlib import Path

from pull_berlin.serve import make_server


def test_serves_the_map_and_the_exports_from_the_project_root(tmp_path: Path) -> None:
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "index.html").write_text("<title>map</title>")
    (tmp_path / "data" / "out").mkdir(parents=True)
    (tmp_path / "data" / "out" / "facilities.geojson").write_text('{"type": "FeatureCollection"}')

    server = make_server(tmp_path, port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        page = urllib.request.urlopen(base + "/web/index.html").read().decode()
        data = urllib.request.urlopen(base + "/data/out/facilities.geojson")
        assert "<title>map</title>" in page
        assert data.headers["Content-Type"].startswith("application/geo+json")
    finally:
        server.shutdown()
        server.server_close()


def test_only_listens_on_localhost(tmp_path: Path) -> None:
    server = make_server(tmp_path, port=0)
    try:
        assert server.server_address[0] == "127.0.0.1"
    finally:
        server.server_close()
