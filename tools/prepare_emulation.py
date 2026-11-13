#!/usr/bin/env python3
"""Prepare PRIVATE full-flash emulator fixtures. Never communicates with hardware.

These images include the original device's NVS secrets and must not be released
or used as a serial/OTA installer. They model completed migration checkpoints,
not a validated sequence of flash operations.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
from zlib import crc32

from check_migration import assess, digest, read_layout


def encode_table(layout):
    records = b"".join(struct.pack("<HBBII16sI", 0x50AA, kind, subtype,
                                  address, size, name.encode("ascii"), 0)
                       for name, kind, subtype, address, size in layout)
    table = records + b"\xeb\xeb" + b"\xff" * 14 + hashlib.md5(records).digest()
    if len(table) > 0xC00:
        raise ValueError("Too many partitions")
    return table.ljust(0x1000, b"\xff")


def select_first_ota():
    # Stock IDF OTA metadata: ota_seq, 20 reserved bytes, state, CRC of ota_seq.
    # UINT32_MAX state is the stock bootloader's non-rollback-managed state.
    seq = struct.pack("<I", 1)
    return seq + b"\xff" * 24 + struct.pack("<I", crc32(seq, 0xFFFFFFFF))


def fixtures(backup_a, backup_b, application, layout):
    report = assess(backup_a, backup_b, application, layout)
    if [(p[3], p[4]) for p in layout if p[1] == 0] != [
            (0x10000, 0xF0000), (0x100000, 0x180000), (0x280000, 0x180000)]:
        raise ValueError("Only the stock-and-dual-proxy candidate is modeled")
    result = {"original": backup_a}
    data = bytearray(backup_a)
    stock = backup_a[0x210000:0x210000 + report["preserved_stock"]["size"]]
    data[0x10000:0x110000] = b"\xff" * 0x100000
    data[0x10000:0x10000 + len(stock)] = stock
    data[0xD000:0xF000] = b"\xff" * 0x2000  # factory selected
    result["old-layout-stock-factory"] = bytes(data)
    data[0x100000:] = b"\xff" * 0x300000
    data[0x8000:0x9000] = encode_table(layout)
    data[0x100000:0x100000 + len(application)] = application
    result["new-layout-stock-boot"] = bytes(data)
    data[0xD000:0xD020] = select_first_ota()
    result["new-layout-proxy-trial"] = bytes(data)
    for value in result.values():
        if value[:0x8000] != backup_a[:0x8000] or value[0x9000:0xD000] != backup_a[0x9000:0xD000] or value[0xF000:0x10000] != backup_a[0xF000:0x10000]:
            raise ValueError("Fixture changed bootloader, NVS or PHY")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup_a", type=Path)
    parser.add_argument("backup_b", type=Path)
    parser.add_argument("application", type=Path)
    parser.add_argument("layout", type=Path)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()
    try:
        images = fixtures(args.backup_a.read_bytes(), args.backup_b.read_bytes(),
                          args.application.read_bytes(), read_layout(args.layout))
        args.output_directory.mkdir(mode=0o700)  # refuse an existing destination
        manifest = {"purpose": "PRIVATE_EMULATOR_FIXTURES_NOT_INSTALLER", "images": {}}
        for name, data in images.items():
            path = args.output_directory / (name + ".bin")
            with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
                f.write(data)
            manifest["images"][name] = {"bytes": len(data), "sha256": digest(data)}
        with os.fdopen(os.open(args.output_directory / "manifest.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as f:
            json.dump(manifest, f, indent=2)
            f.write("\n")
    except (ValueError, KeyError, UnicodeError, OSError, struct.error) as error:
        parser.exit(1, f"Emulator fixture preparation rejected inputs ({type(error).__name__}).\n")
    print("Prepared four private emulator fixtures; no hardware writes")


if __name__ == "__main__":
    main()
