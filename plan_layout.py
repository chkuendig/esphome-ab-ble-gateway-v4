#!/usr/bin/env python3
"""Compare offline flash layouts; never opens a network or serial connection."""
import json
from pathlib import Path

root = Path(__file__).resolve().parent
assessment = json.loads((root / "image-assessment.json").read_text())
size = assessment["image"]["size"]
preserved = [
    ("nvs", "data", "nvs", 0x9000, 0x4000),
    ("otadata", "data", "ota", 0xd000, 0x2000),
    ("phy_init", "data", "phy", 0xf000, 0x1000),
]
layouts = {
    "stock-and-dual-proxy": preserved + [
        ("factory", "app", "factory", 0x10000, 0xf0000),
        ("ota_0", "app", "ota_0", 0x100000, 0x180000),
        ("ota_1", "app", "ota_1", 0x280000, 0x180000),
    ],
    "stock-bridge-single-proxy": preserved + [
        ("factory", "app", "factory", 0x10000, 0x100000),
        ("ota_0", "app", "ota_0", 0x110000, 0x100000),
        ("ota_1", "app", "ota_1", 0x210000, 0x1f0000),
    ],
    "dual-proxy-external-stock-backup": preserved + [
        ("ota_0", "app", "ota_0", 0x10000, 0x1f0000),
        ("ota_1", "app", "ota_1", 0x200000, 0x1f0000),
    ],
}
reports = {}
out = root / "layout-candidates"
out.mkdir(exist_ok=True)
for name, parts in layouts.items():
    end = 0x9000
    for label, kind, subtype, start, length in parts:
        assert start >= end, (name, label, "overlap")
        assert start % (0x10000 if kind == "app" else 0x1000) == 0
        assert length % 0x1000 == 0 and length > 0
        end = start + length
    assert end <= 0x400000
    app_slots = [p for p in parts if p[1] == "app" and p[2].startswith("ota_")]
    fits_all = all(size <= p[4] for p in app_slots)
    fits_one = any(size <= p[4] for p in app_slots)
    reports[name] = {
        "image_fits_at_least_one_slot": fits_one,
        "ordinary_two_slot_esphome_ota_size_compatible": fits_all,
        "retains_on_device_stock": any(p[2] == "factory" for p in parts),
        "requires_partition_table_write": True,
        "installation_implemented_or_validated": False,
    }
    (out / (name + ".csv")).write_text(
        "# OFFLINE CANDIDATE ONLY. Not installed or approved for flashing.\n" +
        "# Preserve the existing bootloader and vendor NVS/PHY offsets.\n" +
        "\n".join(f"{label}, {kind}, {subtype}, 0x{start:x}, 0x{length:x},"
                  for label, kind, subtype, start, length in parts) + "\n"
    )
reports["stock_copy_requirement"] = (
    "Factory must contain the verified CURRENT 944400-byte stock image before migration. "
    "The original 984080-byte factory image does not fit the shrunken 983040-byte factory slot."
)
reports["power_loss_boundary"] = (
    "Partition-table sector replacement is not power-failure-safe. "
    "Serial recovery availability must be resolved before execution."
)
(root / "layout-assessment.json").write_text(json.dumps(reports, indent=2) + "\n")
print(json.dumps(reports, indent=2))
