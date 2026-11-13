"""Offline, standard-library inspection of downloaded ESP32 OTA images."""
import hashlib
import json
import re
import struct
from pathlib import Path


def inspect(path):
    data = path.read_bytes()
    assert data[0] == 0xE9, "Not an ESP application image"
    position = 24
    checksum = 0xEF
    segments = []
    for _ in range(data[1]):
        address, length = struct.unpack_from("<II", data, position)
        position += 8
        assert position + length <= len(data)
        segments.append({"offset": position, "address": hex(address), "size": length})
        for value in data[position:position + length]:
            checksum ^= value
        position += length
    image_end = (position + 16) & ~15
    assert checksum == data[image_end - 1], "Image checksum mismatch"
    appended_hash = bool(data[23])
    if appended_hash:
        assert hashlib.sha256(data[:image_end]).digest() == data[image_end:image_end + 32]
    strings = [(match.start(), match.group().decode())
               for match in re.finditer(rb"[ -~]{4,}", data)]
    descriptor = segments[0]["offset"]
    assert struct.unpack_from("<I", data, descriptor)[0] == 0xABCD5432
    fields = {}
    for name, offset, length in [("app_version", 16, 32), ("project", 48, 32),
                                 ("build_time", 80, 16), ("build_date", 96, 16),
                                 ("idf_version", 112, 32)]:
        fields[name] = data[descriptor + offset:descriptor + offset + length].split(b"\0")[0].decode()
    # A heuristic only: compressed images or application-only ARM payloads may
    # lack an obvious vector table. No match does not prove no Nordic code.
    arm_vectors = []
    for offset in range(0, len(data) - 64, 4):
        stack, reset = struct.unpack_from("<II", data, offset)
        if not (0x20000000 < stack <= 0x20010000 and stack % 8 == 0
                and reset & 1 and 0x100 < reset < 0x80000):
            continue
        vectors = struct.unpack_from("<16I", data, offset)[1:]
        if (sum(v == 0 or (v & 1 and 0x100 < v < 0x80000) for v in vectors) >= 14
                and sum(v != 0 for v in vectors) >= 8):
            arm_vectors.append(hex(offset))
    return {
        "file": path.name, "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(), "descriptor": fields,
        "entrypoint": hex(struct.unpack_from("<I", data, 4)[0]),
        "segments": segments, "checksum_valid": True,
        "appended_sha256_valid": appended_hash,
        "bytes_after_image_and_hash": len(data) - image_end - (32 if appended_hash else 0),
        "at_commands": [{"offset": hex(o), "text": s} for o, s in strings if s.startswith("AT+")],
        "nordic_or_gatt_string_matches": [{"offset": hex(o), "text": s} for o, s in strings
                                          if re.search(r"nordic|nrf|dfu|softdevice|gatt", s, re.I)],
        "arm_vector_candidates_heuristic": arm_vectors,
    }
