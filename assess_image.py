#!/usr/bin/env python3
"""Inspect an ESPHome app against the measured stock layout. Never flashes."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("image", type=Path)
args = parser.parse_args()
inspector = ROOT / "tools/inspect_images.py"
spec = importlib.util.spec_from_file_location("esp_image_inspector", inspector)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
image = module.inspect(args.image)
if image["bytes_after_image_and_hash"] != 0:
    raise SystemExit("Expected an application image, not a merged/factory image")
# Measured stock layout; no private dump is needed for this size comparison.
slots = [{"label": "ota_0", "address": 0x110000, "size": 0x100000},
         {"label": "ota_1", "address": 0x210000, "size": 0x100000}]
fits = all(image["size"] <= p["size"] for p in slots) and len(slots) == 2
report = {
    "image": image,
    "stock_slots": slots,
    "fits_stock_slots": fits,
    "direct_vendor_ota_allowed": False,
    "deployment_status": "NOT_INSTALLED",
    "remaining_gates": [
        "Recovery component and bootloader compatibility need verification",
        "Live ESPHome proxy GATT and Nordic MQTT acceptance checks",
    ] + ([] if fits else ["Application exceeds stock OTA slots: migration required"]),
    "source_sha256": {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [ROOT / "xbg-proxy.yaml", *sorted((ROOT / "components/ab_nordic").glob("*"))]
        if p.is_file()
    },
}
(ROOT / "image-assessment.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({"application_bytes": image["size"], "stock_slot_bytes": [p["size"] for p in slots],
                  "fits_stock_slots": fits, "sha256": image["sha256"],
                  "installed": False}, indent=2))
