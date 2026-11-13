import base64
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("prepare_settings", Path(__file__).resolve().parents[1] / "tools/prepare_settings.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SettingsTests(unittest.TestCase):
    def test_native_layout_and_no_partition_erase(self):
        c = {"wifi-type": 0, "ssid": "Example", "passcode": "example-password"}
        i = {"mac": "00:00:00:00:00:01", "firmwareVer": "1.5.13"}
        result = module.prepare(c, i, bytes(range(32)))
        wifi, api, suppression = result["records"]
        data = base64.b64decode(wifi["value_base64"])
        self.assertEqual(len(data), 98)
        self.assertEqual(data[:33].rstrip(b"\0"), b"Example")
        self.assertEqual(data[33:].rstrip(b"\0"), b"example-password")
        self.assertEqual(wifi["key"], "88491487")
        self.assertEqual(api["key"], "88491486")
        self.assertEqual(base64.b64decode(api["value_base64"]), bytes(range(32)))
        self.assertEqual(suppression["value"], 0)
        self.assertTrue(result["preserve_other_records"])
        self.assertTrue(result["readback_required_before_firmware_switch"])

    def test_limits_and_open_network(self):
        for ssid, password in [("x" * 32, "y" * 64), ("open", "")]:
            self.assertEqual(len(module.encode_wifi({"wifi-type": 0, "ssid": ssid, "passcode": password})), 98)
        for ssid, password in [("", ""), ("x" * 33, ""), ("x", "y" * 65), ("x\0", "")]:
            with self.assertRaises(ValueError):
                module.encode_wifi({"wifi-type": 0, "ssid": ssid, "passcode": password})

    def test_enterprise_and_empty_key_rejected(self):
        with self.assertRaises(ValueError):
            module.encode_wifi({"wifi-type": 1, "ssid": "Example", "passcode": ""})
        with self.assertRaises(ValueError):
            module.prepare({}, {}, bytes(32))


if __name__ == "__main__":
    unittest.main()
