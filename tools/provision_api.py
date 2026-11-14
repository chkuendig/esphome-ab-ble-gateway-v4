#!/usr/bin/env python3
"""Provision a per-device API key over Noise; never accept firmware or reset it.

Requires aioesphomeapi (tested with 46.25.0). The input is the PRIVATE bundle
from prepare_settings.py. Output is a PRIVATE connection file for HA setup.
"""
import argparse
import asyncio
import base64
import json
import os
from pathlib import Path

from aioesphomeapi import APIClient, ZERO_NOISE_PSK


async def provision(host, settings, output):
    record = json.loads(settings.read_text())
    key = next(r["value_base64"] for r in record["records"]
               if r["namespace"] == "esphome" and r["key"] == "88491486")
    raw_key = base64.b64decode(key, validate=True)
    if len(raw_key) != 32 or not any(raw_key):
        raise ValueError("Invalid per-device key")
    mac = record["device_mac"].replace(":", "").replace("-", "").lower()
    if len(mac) != 12 or any(c not in "0123456789abcdef" for c in mac):
        raise ValueError("Invalid expected device identity")
    if output.exists():
        raise FileExistsError("Refusing to overwrite a private connection file")
    connected = None
    for attempt in (key, ZERO_NOISE_PSK):
        client = APIClient(host, 6053, noise_psk=attempt, expected_mac=mac)
        try:
            await asyncio.wait_for(client.connect(login=True), 20)
            connected = client
            break
        except Exception:
            await client.disconnect()
    if connected is None:
        raise RuntimeError("Encrypted connection failed; no settings changed")
    try:
        info = await connected.device_info()
        if not info.name.startswith("ab-ble-gateway-v4"):
            raise ValueError("Unexpected firmware identity")
        if info.api_encryption_provisionable:
            # This API field carries base64 text as bytes, not the raw 32 bytes.
            if not await connected.noise_encryption_set_key(key.encode("ascii")):
                raise RuntimeError("Device rejected the key")
        await connected.disconnect()
        connected = APIClient(host, 6053, noise_psk=key, expected_mac=mac)
        await asyncio.wait_for(connected.connect(login=True), 20)
        info = await connected.device_info()
        if info.api_encryption_provisionable:
            raise RuntimeError("Private-key reconnect did not verify provisioning")
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump({"host": host, "port": 6053, "noise_psk": key,
                       "mac": record["device_mac"], "name": info.name}, f, indent=2)
            f.write("\n")
        print("Private encrypted API connection verified. Firmware remains unaccepted.")
    finally:
        await connected.disconnect()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host")
    parser.add_argument("settings", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    asyncio.run(provision(args.host, args.settings, args.output))


if __name__ == "__main__":
    main()
