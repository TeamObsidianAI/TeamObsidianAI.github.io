#!/usr/bin/env python3
"""
Local dashboard server for the Product Trend Pipeline.

Run this instead of opening trend-report.html directly:
    python server.py

Then visit http://localhost:8765 in your browser.
The "Run Pipeline Now" button on the dashboard will trigger main.py
and stream its output live in the browser.
"""

import json
import os
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PORT = 8765
PIPELINE_DIR = Path(__file__).parent
SITE_DIR = PIPELINE_DIR.parent

_pipeline_state = {"running": False, "log": [], "started_at": None, "finished_at": None}
_state_lock = threading.Lock()


def run_pipeline():
    with _state_lock:
        if _pipeline_state["running"]:
            return
        _pipeline_state["running"] = True
        _pipeline_state["log"] = []
        _pipeline_state["started_at"] = time.time()
        _pipeline_state["finished_at"] = None

    try:
        proc = subprocess.Popen(
            [sys.executable, "main.py"],
            cwd=str(PIPELINE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        for line in proc.stdout:
            line = line.rstrip()
            with _state_lock:
                _pipeline_state["log"].append(line)
        proc.wait()
    finally:
        with _state_lock:
            _pipeline_state["running"] = False
            _pipeline_state["finished_at"] = time.time()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # silence access log

    def _json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path):
        if not path.exists():
            self.send_response(404)
            self.end_headers()
            return
        ctype = (
            "text/html" if path.suffix == ".html"
            else "application/json" if path.suffix == ".json"
            else "text/css" if path.suffix == ".css"
            else "application/octet-stream"
        )
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        p = self.path.split("?")[0]

        if p == "/api/status":
            with _state_lock:
                state = dict(_pipeline_state)
                state["log"] = list(state["log"])
            self._json(state)

        elif p == "/trend-data.json":
            self._file(SITE_DIR / "trend-data.json")

        elif p in ("/", "/trend-report.html"):
            self._file(SITE_DIR / "trend-report.html")

        else:
            candidate = SITE_DIR / p.lstrip("/")
            self._file(candidate)

    def do_POST(self):
        if self.path == "/api/run":
            with _state_lock:
                already_running = _pipeline_state["running"]
            if already_running:
                self._json({"ok": False, "message": "Pipeline already running"}, 409)
            else:
                t = threading.Thread(target=run_pipeline, daemon=True)
                t.start()
                self._json({"ok": True, "message": "Pipeline started"})
        else:
            self.send_response(404)
            self.end_headers()


def main():
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"\n  Product Trend Pipeline — Dashboard Server")
    print(f"  Open in browser: {url}")
    print(f"  Press Ctrl+C to stop\n")
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")


if __name__ == "__main__":
    main()
