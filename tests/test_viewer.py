"""The run folder has everything the viewer needs, and the viewer serves only those files."""
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

import view_city
from core.prices import SimulatedFeed
from run_city import build_city, new_run_dir, run_city, START_PRICES


@pytest.fixture
def finished_run():
    run_dir = new_run_dir()
    run_city(SimulatedFeed(START_PRICES, seed=3), cycles=25, raphael=build_city(run_dir=run_dir))
    return run_dir


def test_run_folder_has_meta_events_audit_ledger(finished_run):
    names = {p.name for p in finished_run.iterdir()}
    assert {"meta.json", "events.jsonl", "audit.json", "ledger.json"} <= names
    meta = json.loads((finished_run / "meta.json").read_text())
    assert meta["run_id"] == finished_run.name
    assert meta["watchlist"] == list(START_PRICES)
    assert meta["cycles"] == 25
    audit = json.loads((finished_run / "audit.json").read_text())
    assert audit["ok"] is True


def test_latest_run_picks_newest_with_events(tmp_path):
    assert view_city.latest_run(tmp_path / "nothing") is None
    old, new, empty = tmp_path / "20260101-000000", tmp_path / "20260102-000000", tmp_path / "20260103-000000"
    for d in (old, new, empty):
        d.mkdir()
    (old / "events.jsonl").write_text("")
    (new / "events.jsonl").write_text("")
    assert view_city.latest_run(tmp_path) == new  # "empty" has no events yet


@pytest.fixture
def server(finished_run):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), view_city.make_handler(finished_run))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def fetch(url):
    with urllib.request.urlopen(url) as r:
        return r.status, r.read().decode("utf-8"), r.headers


def test_serves_viewer_and_run_files(server, finished_run):
    status, body, _ = fetch(server + "/")
    assert status == 200 and "city.js" in body
    status, body, headers = fetch(server + "/run/events.jsonl")
    assert body == (finished_run / "events.jsonl").read_bytes().decode("utf-8")
    assert "\r" not in body
    assert headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("path", ["/run/../../config/settings.py", "/run/secret.txt", "/run/"])
def test_refuses_anything_but_run_files(server, path):
    with pytest.raises(urllib.error.HTTPError) as err:
        fetch(server + path)
    assert err.value.code == 404
