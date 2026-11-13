#!/usr/bin/env python3
"""Prepare PRIVATE NVS records from a read-only stock settings backup. No flashing.

The installer must apply these records through NVS APIs while preserving all
other namespaces, then verify readback BEFORE switching to the generic image.
This file is a staging contract, not an installer or a partition image.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets


def encode_wifi(connection):
    if connection.get("wifi-type") != 0:
        raise ValueError("Only personal Wi-Fi migration is implemented")
    ssid = connection["ssid"].encode("utf-8")
    password = connection["passcode"].encode("utf-8")
    if not 1 <= len(ssid) <= 32 or len(password) > 64 or b"\0" in ssid + password:
        raise ValueError("Invalid Wi-Fi credentials")
    return ssid.ljust(33, b"\0") + password.ljust(65, b"\0")


def prepare(connection, info, api_key):
    if len(api_key) != 32 or not any(api_key):
        raise ValueError("API key must contain 32 nonzero-random bytes")
    wifi = encode_wifi(connection)
    return {
        "schema": 1,
        "status": "PRIVATE_STAGING_ONLY_NOT_APPLIED",
        "device_mac": info["mac"],
        "stock_firmware": info["firmwareVer"],
        "records": [
            {"namespace": "esphome", "key": "88491487", "type": "blob",
             "value_base64": base64.b64encode(wifi).decode()},
            {"namespace": "esphome", "key": "88491486", "type": "blob",
             "value_base64": base64.b64encode(api_key).decode()},
            {"namespace": "ab_migration", "key": "reset", "type": "u8", "value": 0},
        ],
        "preserve_other_records": True,
        "readback_required_before_firmware_switch": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup", type=Path, help="PRIVATE directory containing stock-connection.json and stock-info.json")
    parser.add_argument("output", type=Path, help="PRIVATE output file; must not exist")
    args = parser.parse_args()
    connection = json.loads((args.backup / "stock-connection.json").read_text())
    info = json.loads((args.backup / "stock-info.json").read_text())
    document = prepare(connection, info, secrets.token_bytes(32))
    encoded = (json.dumps(document, indent=2) + "\n").encode()
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    print("Private staging records prepared; no device changes.")
    print("SHA256:", hashlib.sha256(encoded).hexdigest())


if __name__ == "__main__":
    main()
