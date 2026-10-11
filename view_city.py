"""Zombiso AI City viewer: watch a run in the browser.

    python view_city.py                 # newest run in data/runs (follows it live)
    python view_city.py data/runs/XYZ   # a specific run
    python view_city.py --port 9000 --no-open

Serves viewer/ plus the run's files under /run/. Local only (127.0.0.1).
Without a run folder argument, /run/ always points at the newest run, so you
can start the viewer first and then `python run_city.py --delay 0.5`.
"""
import argparse
import http.server
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VIEWER_DIR = ROOT / "viewer"
RUNS_DIR = ROOT / "data" / "runs"
RUN_FILES = {"meta.json", "events.jsonl", "audit.json", "ledger.json"}


def latest_run(runs_dir=RUNS_DIR):
    """Newest run folder that has started writing events, or None."""
    if not runs_dir.is_dir():
        return None
    runs = sorted(p for p in runs_dir.iterdir() if (p / "events.jsonl").exists())
    return runs[-1] if runs else None


def make_handler(fixed_run=None):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(VIEWER_DIR), **kwargs)

        def translate_path(self, path):
            clean = path.split("?", 1)[0].split("#", 1)[0]
            if clean.startswith("/run/"):
                name = clean[len("/run/"):]
                run = fixed_run or latest_run()
                if run is None or name not in RUN_FILES:
                    return str(VIEWER_DIR / "__missing__")
                return str(run / name)
            return super().translate_path(path)

        def end_headers(self):
            # run files change while a run is live; viewer files change on every update
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def log_message(self, fmt, *args):
            pass  # the viewer polls every second; keep the terminal quiet

    return Handler


def main():
    parser = argparse.ArgumentParser(description="Watch a Zombiso AI City run in the browser.")
    parser.add_argument("run", nargs="?", help="run folder (default: newest, followed live)")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true", help="don't open a browser tab")
    args = parser.parse_args()

    fixed_run = Path(args.run).resolve() if args.run else None
    if fixed_run and not (fixed_run / "events.jsonl").exists():
        parser.error(f"{fixed_run} has no events.jsonl")

    server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(fixed_run))
    url = f"http://127.0.0.1:{args.port}/"
    what = fixed_run.name if fixed_run else "newest run (live)"
    print(f"Zombiso AI City viewer: {url}  [{what}]  Ctrl+C to stop")
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
