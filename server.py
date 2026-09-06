#!/usr/bin/env python3
"""Serve the NQ Pine backtester UI."""

from __future__ import annotations

import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "web"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))


def main() -> int:
    parser = argparse.ArgumentParser(description="NQ Pine backtest server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print("NQ Pine backtest: http://%s:%s" % (args.host, args.port))
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
