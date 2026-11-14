"""nRF52832 scanner fed from the gateway's ESPHome serial proxy."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from homeassistant.components.bluetooth import MONOTONIC_TIME, BaseHaRemoteScanner
from homeassistant.core import HomeAssistant
from yarl import URL

from .const import BAUD_RATE, RECONNECT_MAX_SECONDS, RECONNECT_MIN_SECONDS
from .protocol import NordicAdvert, NordicParser

_LOGGER = logging.getLogger(__name__)


class NordicScanner(BaseHaRemoteScanner):
    """Passive, non-connectable scanner for the gateway's nRF52832 radio."""

    def async_on_adverts(self, adverts: list[NordicAdvert]) -> None:
        """Hand parsed advertisements to Home Assistant's Bluetooth manager."""
        now = MONOTONIC_TIME()
        on_raw = self._async_on_raw_advertisement
        for advert in adverts:
            # The UART carries the PDU event type, not public/random address
            # type. This scanner is never used for connections.
            on_raw(advert.address, advert.rssi, advert.data, {"event_type": advert.event_type}, now)


def serial_proxy_url(esphome_entry_id: str, port_name: str) -> str:
    """Canonical URL of the port, as Home Assistant's ESPHome integration builds it.

    The port reports no identity, so HA addresses it by name. It reuses the ESPHome integration's existing API connection, so this
    integration never opens a second client or touches the BLE proxy's single
    advertisement subscription.
    """
    return str(
        URL.build(
            scheme="esphome-hass",
            host="esphome",
            path=f"/{esphome_entry_id}",
            query={"port_name": port_name},
        )
    )


class _StreamProtocol(asyncio.Protocol):
    def __init__(self, link: NordicLink) -> None:
        self._link = link
        self.closed: asyncio.Future[Exception | None] = asyncio.get_running_loop().create_future()

    def data_received(self, data: bytes) -> None:
        self._link.on_data(data)

    def connection_lost(self, exc: Exception | None) -> None:
        if not self.closed.done():
            self.closed.set_result(exc)


class NordicLink:
    """Keeps a read-only serial proxy subscription alive and feeds the scanner."""

    def __init__(self, hass: HomeAssistant, url: str, scanner: NordicScanner) -> None:
        self._hass = hass
        self._url = url
        self._scanner = scanner
        self._parser = NordicParser()
        self._transport: asyncio.BaseTransport | None = None
        self._stopping = False
        self.connected = False
        self.connects = 0
        self.bytes_received = 0
        self.last_error: str | None = None
        self.connected_since: float | None = None

    def on_data(self, data: bytes) -> None:
        self.bytes_received += len(data)
        if adverts := self._parser.feed(data):
            self._scanner.async_on_adverts(adverts)

    async def run(self) -> None:
        """Connect, stream until the connection drops, then retry with backoff."""
        # Imported lazily: serialx is provided by Home Assistant's ESPHome/usb stack.
        from serialx import create_serial_connection  # noqa: PLC0415

        delay = RECONNECT_MIN_SECONDS
        while not self._stopping:
            protocol: _StreamProtocol | None = None
            try:
                self._transport, protocol = await create_serial_connection(
                    asyncio.get_running_loop(),
                    lambda: _StreamProtocol(self),
                    self._url,
                    baudrate=BAUD_RATE,
                )
            except Exception as err:  # noqa: BLE001 - any failure means retry later
                self._note_error(f"connect failed: {err!r}")
            else:
                self.connected = True
                self.connects += 1
                self.connected_since = time.time()
                self.last_error = None
                delay = RECONNECT_MIN_SECONDS
                _LOGGER.info("nRF52832 scanner stream connected (%s)", self._scanner.name)
                exc = await protocol.closed
                self.connected = False
                self.connected_since = None
                self._transport = None
                self._parser.reset()
                if self._stopping:
                    break
                self._note_error(f"stream closed: {exc!r}")
            await asyncio.sleep(delay)
            delay = min(delay * 2, RECONNECT_MAX_SECONDS)

    def _note_error(self, message: str) -> None:
        if message != self.last_error:
            _LOGGER.warning("nRF52832 scanner %s: %s; retrying", self._scanner.name, message)
        self.last_error = message

    def stop(self) -> None:
        """Release the serial proxy; the firmware then drops nRF52832 adverts."""
        self._stopping = True
        if self._transport is not None:
            self._transport.close()

    def diagnostics(self) -> dict[str, Any]:
        return {
            "url_scheme": self._url.split("://", 1)[0],
            "connected": self.connected,
            "connected_since": self.connected_since,
            "connects": self.connects,
            "bytes_received": self.bytes_received,
            "records": self._parser.records,
            "malformed": self._parser.malformed,
            "discarded_bytes": self._parser.discarded_bytes,
            "last_error": self.last_error,
        }
