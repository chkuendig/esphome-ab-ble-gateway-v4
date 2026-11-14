#!/usr/bin/env python3
"""Stage a verified app on a temporary restricted LAN server; never flash it."""
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import ipaddress
import json
import os
from pathlib import Path
import secrets
import time

from check_migration import assess, read_layout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup_a", type=Path)
    parser.add_argument("backup_b", type=Path)
    parser.add_argument("application", type=Path)
    parser.add_argument("output", type=Path, help="New PRIVATE JSON file for the temporary URL")
    parser.add_argument("--bind-ip", required=True, type=ipaddress.IPv4Address)
    parser.add_argument("--gateway-ip", required=True, type=ipaddress.IPv4Address)
    parser.add_argument("--port", type=int, default=18081)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535 or args.bind_ip.is_unspecified:
        parser.error("Use a reachable LAN address and an unprivileged TCP port")
    payload = args.application.read_bytes()
    layout = Path(__file__).resolve().parents[1] / "layout-candidates/original-stock.csv"
    report = assess(args.backup_a.read_bytes(), args.backup_b.read_bytes(), payload, read_layout(layout))
    prefix = "/esphome-migration/" + secrets.token_hex(24)
    path = prefix + "/1.5.13/ota.bin"
    state = {"base_url": f"http://{args.bind_ip}:{args.port}{prefix}",
             "sha256": report["candidate"]["sha256"], "size": len(payload),
             "expires_after_seconds": 1200, "device_writes": False}

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        def log_message(self, *unused):
            pass  # Never log the private URL.

        def serve(self, body):
            if self.client_address[0] != str(args.gateway_ip) or self.path != path:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if body:
                self.wfile.write(payload)

        def do_GET(self):
            self.serve(True)

        def do_HEAD(self):
            self.serve(False)

    with HTTPServer((str(args.bind_ip), args.port), Handler) as server:
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(state, f, indent=2)
            f.write("\n")
        print("Verified app staged. Private URL saved; no device configuration changed.", flush=True)
        server.timeout = 1
        deadline = time.monotonic() + 1200
        while time.monotonic() < deadline:
            server.handle_request()


if __name__ == "__main__":
    main()
