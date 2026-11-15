import hashlib
import importlib.util
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("serve_migration", ROOT / "tools/serve_migration.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def app(payload_size=256, project=b"ab-ble-gateway-v4"):
    header = bytearray(24)
    header[0], header[1], header[23] = 0xE9, 1, 1
    desc = bytearray(payload_size)
    struct.pack_into("<I", desc, 0, 0xABCD5432)
    desc[48:48 + len(project)] = project
    data = bytes(header) + struct.pack("<II", 0x3F400020, len(desc)) + bytes(desc)
    checksum = 0xEF
    for value in desc:
        checksum ^= value
    data += bytes(15 - len(data) % 16) + bytes([checksum])
    return data + hashlib.sha256(data).digest()


class ImageTests(unittest.TestCase):
    def test_valid_image(self):
        data = app()
        info = m.image(data)
        self.assertEqual(info["project"], "ab-ble-gateway-v4")
        self.assertEqual(info["size"], len(data))

    def test_slot_boundary(self):
        exact = app(0x100000 - 80)
        self.assertEqual(len(exact), m.SLOT_SIZE)
        m.image(exact)
        with self.assertRaises(ValueError):
            m.image(app(0x100000 - 64))

    def test_rejects_damaged_or_merged_images(self):
        data = app()
        corrupt = bytearray(data)
        corrupt[40] ^= 1
        for candidate in (bytes(corrupt), data + b"\xff" * 16, data[:-1], b"\xe9" + data[1:20]):
            with self.subTest(size=len(candidate)), self.assertRaises(ValueError):
                m.image(candidate)

    def test_reports_project_name(self):
        self.assertEqual(m.image(app(project=b"xin-ble-gateway"))["project"], "xin-ble-gateway")


if __name__ == "__main__":
    unittest.main()
