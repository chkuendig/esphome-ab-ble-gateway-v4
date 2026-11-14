"""Tests for the HA integration's SCAN2 parser (custom_components/ab_nordic/protocol.py)."""
import importlib.util
from pathlib import Path
import random
import sys
import unittest

_PATH = Path(__file__).resolve().parents[1] / "custom_components" / "ab_nordic" / "protocol.py"
_SPEC = importlib.util.spec_from_file_location("ab_nordic_protocol", _PATH)
protocol = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = protocol  # dataclasses resolve annotations via sys.modules
_SPEC.loader.exec_module(protocol)

MAC = bytes.fromhex("123456789abc")


def record(data, rssi=-70, event=0, mac=MAC):
    return b"OK+SCAN:" + mac + bytes([rssi & 0xFF, event, len(data)]) + data + b"\r\n"


class ParserTest(unittest.TestCase):
    def test_single_record_fields(self):
        data = bytes.fromhex("020106") + b"\x05\x16\x95\xfe\x71\x20"
        (advert,) = protocol.NordicParser().feed(record(data, rssi=-92, event=3))
        self.assertEqual(advert.address, "12:34:56:78:9A:BC")
        self.assertEqual(advert.rssi, -92)
        self.assertEqual(advert.event_type, 3)
        self.assertEqual(advert.data, data)

    def test_crlf_inside_payload_uses_binary_length(self):
        data = b"\x04\xff\x0d\x0a\x0d"
        (advert,) = protocol.NordicParser().feed(record(data))
        self.assertEqual(advert.data, data)

    def test_byte_by_byte_and_command_replies_between_records(self):
        stream = b"OK\r\nOK+SCAN2\r\n" + record(b"\x02\x01\x06") + b"OK\r\n" + record(b"", event=4)
        parser = protocol.NordicParser()
        adverts = []
        for byte in stream:
            adverts += parser.feed(bytes([byte]))
        self.assertEqual([a.data for a in adverts], [b"\x02\x01\x06", b""])
        self.assertEqual(adverts[1].event_type, 4)
        self.assertEqual(parser.malformed, 0)

    def test_resync_after_mid_record_start_and_corruption(self):
        good = record(b"\x02\x01\x06")
        bad_length = b"OK+SCAN:" + MAC + bytes([0xB0, 0, 40]) + b"x" * 40 + b"\r\n"
        bad_type = b"OK+SCAN:" + MAC + bytes([0xB0, 9, 0]) + b"\r\n"
        bad_tail = b"OK+SCAN:" + MAC + bytes([0xB0, 0, 1]) + b"zXY"
        parser = protocol.NordicParser()
        adverts = parser.feed(good[5:] + bad_length + bad_type + bad_tail + good)
        self.assertEqual(len(adverts), 1)
        self.assertEqual(parser.malformed, 3)

    def test_random_chunking_matches_whole_stream(self):
        rng = random.Random(4)
        records = [record(bytes(rng.randrange(256) for _ in range(rng.randrange(32))),
                          rssi=-rng.randrange(30, 100), event=rng.randrange(5)) for _ in range(200)]
        stream = b"".join(records)
        whole = protocol.NordicParser().feed(stream)
        parser, chunked, i = protocol.NordicParser(), [], 0
        while i < len(stream):
            n = rng.randrange(1, 64)
            chunked += parser.feed(stream[i:i + n])
            i += n
        self.assertEqual(len(whole), 200)
        self.assertEqual(whole, chunked)

    def test_noise_is_bounded(self):
        parser = protocol.NordicParser()
        self.assertEqual(parser.feed(b"\x00" * 10000), [])
        self.assertLess(len(parser._buffer), len(protocol.PREFIX))


if __name__ == "__main__":
    unittest.main()
