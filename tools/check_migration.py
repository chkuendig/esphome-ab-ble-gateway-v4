#!/usr/bin/env python3
"""Read-only migration preflight. Never connects to a device or writes flash.

Accepts private full-flash backups; emits only geometry, hashes and blockers.
The supported starting layout is deliberately narrow: the inspected V4 unit.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import struct

FLASH_SIZE = 0x400000
TABLE_OFFSET = 0x8000
SECTOR_SIZE = 0x1000
STOCK_SHA256 = "68f542ab048cf1b171dc8da3f44dfc5d94f5f801a21cf42e091cee572332dda0"
EXPECTED = [
    ("nvs", 1, 2, 0x9000, 0x4000),
    ("otadata", 1, 0, 0xD000, 0x2000),
    ("phy_init", 1, 1, 0xF000, 0x1000),
    ("factory", 0, 0, 0x10000, 0x100000),
    ("ota_0", 0, 16, 0x110000, 0x100000),
    ("ota_1", 0, 17, 0x210000, 0x100000),
]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def image(data, *, padded=False):
    """Validate an unsigned ESP32 app and return its exact byte extent."""
    if len(data) < 24 or data[0] != 0xE9 or not 1 <= data[1] <= 16:
        raise ValueError("Missing ESP application header")
    if struct.unpack_from("<H", data, 12)[0] != 0 or data[23] not in (0, 1):
        raise ValueError("Unsupported chip or image hash format")
    position, checksum = 24, 0xEF
    for index in range(data[1]):
        if position + 8 > len(data):
            raise ValueError("Truncated segment header")
        _, length = struct.unpack_from("<II", data, position)
        position += 8
        if length > len(data) - position:
            raise ValueError("Truncated segment data")
        if index == 0 and (length < 256 or struct.unpack_from("<I", data, position)[0] != 0xABCD5432):
            raise ValueError("Missing application descriptor")
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
    if not padded and end != len(data):
        raise ValueError("Expected an app-only image with no trailing data")
    return {"size": end, "sha256": digest(data[:end])}


def partitions(data):
    if len(data) != SECTOR_SIZE:
        raise ValueError("Partition table must be one sector")
    entries = []
    for offset in range(0, 0xC00, 32):
        record = data[offset:offset + 32]
        if record[:2] == b"\xeb\xeb":
            if record[2:16] != b"\xff" * 14 or hashlib.md5(data[:offset]).digest() != record[16:]:
                raise ValueError("Invalid partition table MD5")
            validate_layout(entries)
            return entries
        magic, kind, subtype, address, size, label, flags = struct.unpack("<HBBII16sI", record)
        if magic != 0x50AA or flags:
            raise ValueError("Unsupported partition record or flags")
        entries.append((label.split(b"\0")[0].decode("ascii"), kind, subtype, address, size))
    raise ValueError("Missing partition table MD5")


def validate_layout(entries):
    end, names = TABLE_OFFSET + SECTOR_SIZE, set()
    for name, kind, subtype, address, size in sorted(entries, key=lambda p: p[3]):
        if name in names or not name or kind not in (0, 1):
            raise ValueError("Duplicate/unsupported partition")
        names.add(name)
        alignment = 0x10000 if kind == 0 else SECTOR_SIZE
        if size <= 0 or size % SECTOR_SIZE or address % alignment:
            raise ValueError("Invalid partition alignment or size")
        if address < end or address + size > FLASH_SIZE:
            raise ValueError("Partition overlap or flash overflow")
        end = address + size


def read_layout(path):
    result = []
    kinds = {"app": 0, "data": 1}
    subtypes = {"nvs": 2, "ota": 0, "phy": 1, "factory": 0, "ota_0": 16, "ota_1": 17}
    for row in csv.reader(path.read_text().splitlines()):
        if not row or row[0].lstrip().startswith("#"):
            continue
        row = [s.strip() for s in row]
        if len(row) != 6 or row[5]:
            raise ValueError("Only explicit, unencrypted layout rows are supported")
        name, kind, subtype, address, size, _ = row
        result.append((name, kinds[kind], subtypes[subtype], int(address, 0), int(size, 0)))
    validate_layout(result)
    return result


def assess(backup_a, backup_b, candidate, target):
    if len(backup_a) != FLASH_SIZE or backup_a != backup_b:
        raise ValueError("Need two matching 4 MiB flash backups")
    current = partitions(backup_a[TABLE_OFFSET:TABLE_OFFSET + SECTOR_SIZE])
    if current != EXPECTED:
        raise ValueError("Backup layout differs from the inspected stock layout")
    validate_layout(target)
    if [p for p in target if p[1] == 1] != EXPECTED[:3]:
        raise ValueError("Candidate must preserve NVS, OTA metadata and PHY partitions")
    factory = next((p for p in target if p[:3] == ("factory", 0, 0)), None)
    if factory is None or factory[3] != 0x10000:
        raise ValueError("Candidate must retain stock factory recovery")
    stock_slot = EXPECTED[-1]
    stock = image(backup_a[stock_slot[3]:stock_slot[3] + stock_slot[4]], padded=True)
    if stock["sha256"] != STOCK_SHA256 or stock["size"] > factory[4]:
        raise ValueError("Verified current stock image missing or too large for recovery")
    app = image(candidate)
    slots = [p for p in target if p[1] == 0 and p[2] in (16, 17)]
    if len(slots) != 2 or {p[2] for p in slots} != {16, 17} or any(app["size"] > p[4] for p in slots):
        raise ValueError("Application must fit both proposed OTA slots")
    old_factory = image(backup_a[0x10000:0x110000], padded=True)
    needs_table_change = target != current
    blockers = ["Offline input checks do not validate this device or candidate on hardware"]
    if needs_table_change:
        blockers.insert(0, "A power loss during partition-table erase/write can prevent all application boots")
    return {
        "status": "OFFLINE_CHECK_ONLY", "device_writes": False,
        "remote_install_ready": False,
        "backups_identical": True, "backup_sha256": digest(backup_a),
        "candidate": app, "preserved_stock": stock,
        "existing_factory": old_factory,
        "existing_factory_fits_new_recovery": old_factory["size"] <= factory[4],
        "must_replace_old_factory_with_verified_stock": old_factory["sha256"] != stock["sha256"],
        "fits_existing_ota_slots": all(app["size"] <= p[4] for p in EXPECTED[-2:]),
        "partition_table_change_required": needs_table_change,
        "nvs_and_phy_geometry_preserved": True,
        "blockers": blockers,
        "current_layout": current, "proposed_layout": target,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup_a", type=Path)
    parser.add_argument("backup_b", type=Path)
    parser.add_argument("application", type=Path)
    parser.add_argument("layout", type=Path)
    args = parser.parse_args()
    try:
        report = assess(args.backup_a.read_bytes(), args.backup_b.read_bytes(),
                        args.application.read_bytes(), read_layout(args.layout))
    except (ValueError, KeyError, UnicodeError, OSError, struct.error) as error:
        # Never echo a possibly private path, CSV value or exception content.
        parser.exit(1, f"Migration preflight rejected inputs ({type(error).__name__}).\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
