#!/usr/bin/env python3
"""Bounded, read-only Nordic queries over the optional encrypted serial proxy.

Run with the pinned ESPHome environment's aioesphomeapi. Never resets, accepts
firmware, changes Nordic settings, enters DFU or writes sensor characteristics.
Raw RX and timing are recorded privately; byte chunks are not response lines.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import time

from aioesphomeapi import APIClient

# These query forms were already used by the earlier diagnostic firmware.
QUERIES = {"status": b"AT\r\n", "version": b"AT+VERS?\r\n",
           "connection": b"AT+CONN?\r\n", "role": b"AT+ROLE?\r\n",
           "remote_address": b"AT+RADD?\r\n", "rssi": b"AT+RSSI?\r\n"}


def require_ok(response):
    if response is None or int(response.status) != 0:
        raise RuntimeError("Serial proxy did not acknowledge exclusive access")


async def probe(client, queries, record):
    entities, _ = await client.list_entities_services()
    button = next((e for e in entities if type(e).__name__ == "ButtonInfo"
                   and e.name == "Begin Nordic Diagnostics"), None)
    if button is None:
        raise RuntimeError("Diagnostic firmware/button absent; no UART commands sent")
    instance = 0  # This profile declares exactly one serial_proxy.
    remove_callback = client.subscribe_serial_proxy_data(
        lambda msg: record("rx", instance=msg.instance, hex=bytes(msg.data).hex()))
    try:
        client.button_command(button.key)
        # Separate arming and subscribing by a main-loop opportunity. The lease
        # also restores scanning if subscription fails or never happens.
        await asyncio.sleep(0.5)
        require_ok(await client.serial_proxy_subscribe_await_response(instance, timeout=5))
        record("subscribed")
        require_ok(await client.serial_proxy_configure_await_response(instance, 115200, timeout=5))
        await asyncio.sleep(0.3)
        for name in queries:
            data = QUERIES[name]
            record("tx", query=name, hex=data.hex())
            client.serial_proxy_write(instance, data)
            await asyncio.sleep(1.0)
    finally:
        try:
            await client.serial_proxy_unsubscribe_await_response(instance, timeout=5)
            record("unsubscribed")
        finally:
            remove_callback()


async def run(args):
    settings = json.loads(args.connection.read_text())
    client = APIClient(settings["host"], settings.get("port", 6053),
                       noise_psk=settings["noise_psk"],
                       expected_mac=settings["mac"].replace(":", "").lower(),
                       client_info="AB bounded Nordic UART probe")
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as output:
        started = time.monotonic()

        def record(event, **fields):
            output.write(json.dumps({"elapsed": time.monotonic() - started,
                                     "event": event, **fields}) + "\n")
            output.flush()

        try:
            await asyncio.wait_for(client.connect(login=True), 15)
            info = await client.device_info()
            if not info.name.startswith("ab-ble-gateway-v4"):
                raise RuntimeError("Unexpected firmware identity")
            await asyncio.wait_for(probe(client, args.query, record), 30)
            # Firmware restores normal framing and SCAN0/ACT0/SCAN2 on release.
            await asyncio.sleep(1)
            await client.device_info()
            record("api_alive_after_release")
        finally:
            await client.disconnect()
    print("Probe finished; raw replies saved privately. No GATT requests made.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connection", type=Path, required=True,
                        help="Private JSON: host, port, mac, noise_psk")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--query", choices=QUERIES, action="append")
    args = parser.parse_args()
    args.query = args.query or ["status", "version"]
    if len(args.query) > 10:
        parser.error("At most ten paced queries per session")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
