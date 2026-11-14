"""Parser for the April Brother Nordic scanner's binary SCAN2 stream.

Pure Python without Home Assistant imports, so it can be unit tested alone.
Mirrors components/ab_nordic/protocol.c. A record is

    "OK+SCAN:" MAC[6] RSSI[1] EVENT_TYPE[1] LENGTH[1] DATA[LENGTH] "\\r\\n"

The MAC is in printable order (most significant byte first), RSSI is signed
and the event type is the advertising PDU type (0..4), not the address type.
The binary length delimits the record: CR/LF may occur inside DATA.
"""

from __future__ import annotations

from dataclasses import dataclass

PREFIX = b"OK+SCAN:"
MAX_AD = 31
HEADER = len(PREFIX) + 9  # MAC, RSSI, event type, length
MAX_EVENT_TYPE = 4
# Bound the buffer if a stream never yields a record (wrong baud, noise).
MAX_BUFFER = 4096


@dataclass(slots=True, frozen=True)
class NordicAdvert:
    """One advertisement heard by the Nordic radio."""

    address: str
    rssi: int
    event_type: int
    data: bytes


class NordicParser:
    """Incremental, resynchronising SCAN2 parser."""

    def __init__(self) -> None:
        self._buffer = bytearray()
        self.records = 0
        self.malformed = 0
        self.discarded_bytes = 0

    def reset(self) -> None:
        """Drop partial input, e.g. after the transport reconnects."""
        self._buffer.clear()

    def feed(self, chunk: bytes) -> list[NordicAdvert]:
        """Consume bytes and return every complete advertisement."""
        buf = self._buffer
        buf += chunk
        adverts: list[NordicAdvert] = []
        while True:
            start = buf.find(PREFIX)
            if start < 0:
                # Keep a possible partial prefix; the rest is command replies/noise.
                keep = len(PREFIX) - 1
                if len(buf) > keep:
                    self.discarded_bytes += len(buf) - keep
                    del buf[: len(buf) - keep]
                break
            if start:
                self.discarded_bytes += start
                del buf[:start]
            if len(buf) < HEADER:
                break
            event_type = buf[15]
            length = buf[16]
            if length > MAX_AD or event_type > MAX_EVENT_TYPE:
                self._skip_one()
                continue
            end = HEADER + length
            if len(buf) < end + 2:
                break
            if buf[end : end + 2] != b"\r\n":
                self._skip_one()
                continue
            rssi = buf[14] - 256 if buf[14] > 127 else buf[14]
            adverts.append(
                NordicAdvert(
                    address=":".join(f"{b:02X}" for b in buf[8:14]),
                    rssi=rssi,
                    event_type=event_type,
                    data=bytes(buf[HEADER:end]),
                )
            )
            self.records += 1
            del buf[: end + 2]
        if len(buf) > MAX_BUFFER:
            self.discarded_bytes += len(buf) - MAX_BUFFER
            del buf[: len(buf) - MAX_BUFFER]
        return adverts

    def _skip_one(self) -> None:
        """Resynchronise past a false or corrupt prefix."""
        self.malformed += 1
        self.discarded_bytes += 1
        del self._buffer[:1]
