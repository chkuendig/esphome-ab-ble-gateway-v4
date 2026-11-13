import hashlib
import importlib.util
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_migration", ROOT / "tools/check_migration.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def app(payload_size=256):
    header = bytearray(24)
    header[0], header[1], header[23] = 0xE9, 1, 1
    payload = struct.pack("<I", 0xABCD5432) + bytes(payload_size - 4)
    data = bytes(header) + struct.pack("<II", 0x3F400020, len(payload)) + payload
    checksum = 0xEF
    for value in payload:
        checksum ^= value
    data += bytes(15 - len(data) % 16) + bytes([checksum])
    return data + hashlib.sha256(data).digest()


def table():
    records = b"".join(struct.pack("<HBBII16sI", 0x50AA, k, s, a, n, label.encode(), 0)
                       for label, k, s, a, n in m.EXPECTED)
    return (records + b"\xeb\xeb" + b"\xff" * 14 + hashlib.md5(records).digest()).ljust(4096, b"\xff")


class MigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stock = app()
        cls.target = m.read_layout(ROOT / "layout-candidates/stock-and-dual-proxy.csv")
        backup = bytearray(b"\xff" * m.FLASH_SIZE)
        backup[0x8000:0x9000] = table()
        for offset in (0x10000, 0x210000):
            backup[offset:offset + len(cls.stock)] = cls.stock
        cls.backup = bytes(backup)

    def assess(self, backup=None, candidate=None, target=None):
        with patch.object(m, "STOCK_SHA256", m.digest(self.stock)):
            return m.assess(self.backup, backup if backup is not None else self.backup,
                            candidate if candidate is not None else self.stock,
                            target if target is not None else self.target)

    def test_valid_inputs_never_authorize_remote_install(self):
        result = self.assess()
        self.assertFalse(result["remote_install_ready"])
        self.assertFalse(result["device_writes"])
        self.assertTrue(result["partition_table_change_required"])
        self.assertIn("power loss", result["blockers"][0])

    def test_different_backups_rejected_including_nvs(self):
        damaged = bytearray(self.backup)
        damaged[0x9000] ^= 1
        with self.assertRaises(ValueError):
            self.assess(backup=bytes(damaged))

    def test_interrupted_table_write_has_no_valid_table(self):
        expected = table()
        # Model sector erasure and partial reprogramming through its MD5 record.
        for written in (0, 1, 32, 192, 208, 223):
            with self.subTest(written=written), self.assertRaises(ValueError):
                m.partitions(expected[:written] + b"\xff" * (4096 - written))
        self.assertEqual(m.partitions(expected[:224] + b"\xff" * (4096 - 224)), m.EXPECTED)

    def test_corrupt_or_wrong_application_rejected(self):
        corrupt = bytearray(self.stock)
        corrupt[40] ^= 1
        for candidate in (bytes(corrupt), self.stock + b"\x00", app(0x180000)):
            with self.subTest(size=len(candidate)), self.assertRaises(ValueError):
                self.assess(candidate=candidate)
        with self.assertRaises(ValueError):
            m.assess(self.backup, self.backup, self.stock, self.target)

    def test_overlaps_and_settings_movement_rejected(self):
        for index, address in ((0, 0xA000), (4, 0xF0000), (5, 0x300000)):
            changed = list(self.target)
            name, kind, subtype, _, size = changed[index]
            changed[index] = (name, kind, subtype, address, size)
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.assess(target=changed)


if __name__ == "__main__":
    unittest.main()
