#!/usr/bin/env python3
"""Verify network constants in the exact, privately backed-up stock application.

Read-only. Prints no NVS or credentials. Addresses come from the accompanying
Ghidra exports of ota_1-installed.bin, not a downloaded vendor update.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

EXPECTED_SHA256 = "68f542ab048cf1b171dc8da3f44dfc5d94f5f801a21cf42e091cee572332dda0"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--full-flash", type=Path)
    args = parser.parse_args()
    image = args.image.read_bytes()
    digest = hashlib.sha256(image).hexdigest()
    if digest != EXPECTED_SHA256:
        raise SystemExit("Different image: fixed analysis addresses must not be reused")
    segments = []
    pos = 24
    for _ in range(image[1]):
        address, size = struct.unpack_from("<II", image, pos)
        pos += 8
        segments.append((address, image[pos:pos + size]))
        pos += size

    def read(address, size):
        for start, data in segments:
            if start <= address and address + size <= start + len(data):
                return data[address - start:address - start + size]
        raise ValueError(f"Unmapped address {address:#x}")

    def word(address):
        return struct.unpack("<I", read(address, 4))[0]

    assert word(0x400D056C) == 0x40009FDC  # ROM gpio_pad_select_gpio
    mac_defaults = struct.unpack("<9I", read(word(0x400D0C3C), 36))
    assert mac_defaults == (100, 2048, 15, 23, 18, 0, 0, 0, 0)
    phy_defaults = struct.unpack("<4i", read(word(0x400D0C40), 16))
    assert phy_defaults == (-1, 100, 4000, 5)
    # app_netif_init overrides default phy_addr to 1 and reset_gpio_num to -1.
    # Tick divisor setup 4008930c divides CPU frequency by 100 using this
    # signed-division multiplier and right shift of 37 bits.
    assert word(0x40080CA0) == 0x51EB851F
    # 400822b4 returns ROM g_ticks_per_us_pro * 1,000,000 = CPU Hz.
    assert word(0x40080640) == 0x3FFE01E0
    assert word(0x40080644) == 1_000_000
    report = {
        "image_sha256": digest,
        "image_bytes": len(image),
        "app_version": image[0x30:0x50].split(b"\0")[0].decode(),
        "reset_function": "0x400d8cc4",
        "network_init": "0x400d8930",
        "reset_gpio": 13,
        "sequence": ["select GPIO mux", "GPIO_MODE_DISABLE", "vTaskDelay(11)",
                     "GPIO_MODE_OUTPUT", "level 0", "vTaskDelay(2)", "level 1"],
        "phy_constructor": "0x400f1ce8: esp_eth_phy_new_lan87xx",
        "phy_address": 1,
        "driver_reset_gpio": -1,
        "phy_reset_timeout_ms": phy_defaults[1],
        "phy_autoneg_timeout_ms": phy_defaults[2],
        "mdc_gpio": mac_defaults[3],
        "mdio_gpio": mac_defaults[4],
        "rmii_default_resolved_in_mac_constructor": {"mode": "output", "gpio": 17},
        "tick_frequency_hz": 100,
        "reset_delays_nominal_ms": [110, 20],
        "note": "vTaskDelay durations are tick-relative, not precise wall-clock delays; no live reset performed",
    }
    if args.full_flash:
        flash = args.full_flash.read_bytes()
        matched = flash[0x210000:0x210000 + len(image)] == image
        if not matched:
            raise SystemExit("Stock image does not match ota_1 in supplied full backup")
        report["matches_full_backup_ota1"] = True
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
