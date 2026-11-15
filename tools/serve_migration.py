#!/usr/bin/env python3
"""Serve an ESPHome app image to the stock firmware's updater, then exit.

The stock firmware pulls updates from <ota-url>/<its version>/ota.bin. This
server validates the image, answers only the given gateway IP under a random
/esphome-migration/ prefix (any version directory), and stops after 20 minutes.
It never contacts the gateway; set ota-url and trigger the update yourself.
"""
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import hashlib
import ipaddress
from pathlib import Path
import re
import secrets
import struct
import time

SLOT_SIZE = 0x100000  # stock OTA slot (partitions.csv)
PROJECT_NAME = "ab-ble-gateway-v4"
SERVE_SECONDS = 1200


def image(data):
    """Validate an app-only ESP32 image; return its project name, size and SHA256."""
    if len(data) < 24 or data[0] != 0xE9 or not 1 <= data[1] <= 16:
        raise ValueError("Not an ESP32 application image")
    if struct.unpack_from("<H", data, 12)[0] != 0 or data[23] not in (0, 1):
        raise ValueError("Not a classic ESP32 image")
    position, checksum, project = 24, 0xEF, None
    for index in range(data[1]):
        if position + 8 > len(data):
            raise ValueError("Truncated segment header")
        _, length = struct.unpack_from("<II", data, position)
        position += 8
        if length > len(data) - position:
            raise ValueError("Truncated segment data")
        if index == 0:
            if length < 256 or struct.unpack_from("<I", data, position)[0] != 0xABCD5432:
                raise ValueError("Missing application descriptor")
            project = data[position + 48:position + 80].split(b"\0", 1)[0].decode("ascii", "replace")
        for value in data[position:position + length]:
            checksum ^= value
        position += length
    end = (position + 16) & ~15
    if end > len(data) or data[end - 1] != checksum:
        raise ValueError("Invalid image checksum")
    if data[23]:
        if hashlib.sha256(data[:end]).digest() != data[end:end + 32]:
            raise ValueError("Invalid appended image hash")
        end += 32
    if end != len(data):
        raise ValueError("Trailing data: use firmware.ota.bin, not a merged factory image")
    if end > SLOT_SIZE:
        raise ValueError(f"Image is {end} bytes; the stock OTA slot holds {SLOT_SIZE}")
    return {"project": project, "size": end, "sha256": hashlib.sha256(data).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("image", type=Path, help="app-only image, e.g. build/ab-ble-gateway-v4.ota.bin")
    parser.add_argument("--bind-ip", required=True, type=ipaddress.IPv4Address,
                        help="this computer's LAN address")
    parser.add_argument("--gateway-ip", required=True, type=ipaddress.IPv4Address)
    parser.add_argument("--port", type=int, default=18081)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535 or args.bind_ip.is_unspecified:
        parser.error("Use a reachable LAN address and an unprivileged TCP port")
    payload = args.image.read_bytes()
    try:
        info = image(payload)
    except ValueError as err:
        parser.error(str(err))
    if info["project"] != PROJECT_NAME:
        parser.error(f"Image is {info['project']!r}, expected {PROJECT_NAME!r}")
    prefix = "/esphome-migration/" + secrets.token_hex(16)
    wanted = re.compile(re.escape(prefix) + r"/[0-9A-Za-z._-]+/ota\.bin")

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        def log_message(self, *unused):
            pass

        def serve(self, body):
            if self.client_address[0] != str(args.gateway_ip) or not wanted.fullmatch(self.path):
                self.send_error(404)
                return
            print(f"Serving {self.path.rsplit('/', 2)[-2]}/ota.bin to the gateway", flush=True)
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
        print(f"Image OK: {info['size']} bytes, SHA256 {info['sha256']}")
        print(f"Set the gateway's ota-url to:\n  http://{args.bind_ip}:{args.port}{prefix}")
        print(f"Serving for {SERVE_SECONDS // 60} minutes (Ctrl-C to stop).", flush=True)
        server.timeout = 1
        deadline = time.monotonic() + SERVE_SECONDS
        while time.monotonic() < deadline:
            server.handle_request()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
