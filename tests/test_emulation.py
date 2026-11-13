"""Check fixture boundaries using synthetic images, never real device secrets."""
import importlib.util
import struct
import sys
import unittest
from unittest.mock import patch

from test_migration import ROOT, app, table, m

spec = importlib.util.spec_from_file_location("prepare_emulation", ROOT / "tools/prepare_emulation.py")
em = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {"check_migration": m}):
    spec.loader.exec_module(em)


class EmulationTests(unittest.TestCase):
    def setUp(self):
        self.stock, self.candidate = app(), app(512)
        self.layout = m.read_layout(ROOT / "layout-candidates/stock-and-dual-proxy.csv")
        data = bytearray(b"\xff" * m.FLASH_SIZE)
        data[:0x8000] = b"B" * 0x8000
        data[0x8000:0x9000] = table()
        data[0x9000:0xD000] = b"N" * 0x4000
        data[0xF000:0x10000] = b"P" * 0x1000
        for offset in (0x10000, 0x210000):
            data[offset:offset + len(self.stock)] = self.stock
        self.backup = bytes(data)

    def fixtures(self, second=None):
        with patch.object(m, "STOCK_SHA256", m.digest(self.stock)):
            return em.fixtures(self.backup, self.backup if second is None else second,
                               self.candidate, self.layout)

    def test_checkpoints_preserve_bootloader_and_settings(self):
        images = self.fixtures()
        self.assertEqual(images["original"], self.backup)
        for name, data in images.items():
            with self.subTest(name=name):
                self.assertEqual(len(data), m.FLASH_SIZE)
                for start, end in ((0, 0x8000), (0x9000, 0xD000), (0xF000, 0x10000)):
                    self.assertEqual(data[start:end], self.backup[start:end])
                self.assertEqual(data[0x10000:0x10000 + len(self.stock)], self.stock)
        old = images["old-layout-stock-factory"]
        self.assertEqual(m.partitions(old[0x8000:0x9000]), m.EXPECTED)
        self.assertEqual(old[0x210000:0x210000 + len(self.stock)], self.stock)
        for name in ("new-layout-stock-boot", "new-layout-proxy-trial"):
            data = images[name]
            self.assertEqual(m.partitions(data[0x8000:0x9000]), self.layout)
            self.assertEqual(data[0x100000:0x100000 + len(self.candidate)], self.candidate)
            self.assertEqual(data[0x280000:], b"\xff" * 0x180000)

    def test_trial_changes_only_ota_selection(self):
        images = self.fixtures()
        factory, trial = images["new-layout-stock-boot"], images["new-layout-proxy-trial"]
        self.assertEqual(factory[0xD000:0xF000], b"\xff" * 0x2000)
        self.assertEqual(factory[:0xD000], trial[:0xD000])
        self.assertEqual(factory[0xD020:], trial[0xD020:])
        # IDF-compatible sequence 1 selects ota_0, with an undefined OTA state.
        self.assertEqual(struct.unpack("<I20sII", trial[0xD000:0xD020]),
                         (1, b"\xff" * 20, 0xFFFFFFFF, 0x4743989A))

    def test_mismatched_private_settings_rejected(self):
        second = bytearray(self.backup)
        second[0x9000] ^= 1
        with self.assertRaises(ValueError):
            self.fixtures(bytes(second))


if __name__ == "__main__":
    unittest.main()
