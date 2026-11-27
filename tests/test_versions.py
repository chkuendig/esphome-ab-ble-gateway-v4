import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class VersionTests(unittest.TestCase):
    def test_firmware_and_integration_versions_match(self):
        yaml = (ROOT / "ab-ble-gateway-v4.yaml").read_text()
        firmware = re.search(r'^\s+version:\s*"([^"]+)"', yaml, re.M).group(1)
        manifest = json.loads((ROOT / "custom_components/ab_nordic/manifest.json").read_text())
        self.assertEqual(firmware, manifest["version"])


if __name__ == "__main__":
    unittest.main()
