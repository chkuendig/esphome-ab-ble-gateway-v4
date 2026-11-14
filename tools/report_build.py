#!/usr/bin/env python3
"""Report a local app-only build without publishing its bytes or configuration."""
import json
from pathlib import Path

from check_migration import image

root = Path(__file__).resolve().parents[1]
build = root / "private/data/private/build/build"
app = image((build / "firmware.ota.bin").read_bytes())
config = json.loads((build / "config/sdkconfig.json").read_text())
for key, expected in {
    "BT_GATTC_ENABLE": True,
    "BT_GATTS_ENABLE": False,
    "COMPILER_OPTIMIZATION_ASSERTIONS_SILENT": True,
    "LIBC_NEWLIB_NANO_FORMAT": False,
    "VFS_SUPPORT_IO": False,
    "ESP_ERR_TO_NAME_LOOKUP": False,
}.items():
    if bool(config.get(key)) != expected:
        raise SystemExit(f"Unexpected build setting: {key}")

defines = (build.parent / "src/esphome/core/defines.h").read_text()
for key in ("USE_API_NOISE", "USE_OTA_ENCRYPTION_REQUIRED", "USE_BLUETOOTH_PROXY_CONNECTIONS"):
    if f"#define {key}" not in defines:
        raise SystemExit(f"Required feature missing: {key}")
if "#define USE_MQTT" in defines:
    raise SystemExit("Unexpected MQTT component")

print(f"Application: **{app['size']:,} bytes**")
print(f"\nOriginal 1 MiB slot margin: **{0x100000 - app['size']:,} bytes**")
print(f"\nSHA256: `{app['sha256']}`")
print("\nImage checksum/hash and required feature checks passed. Hardware not tested.")
