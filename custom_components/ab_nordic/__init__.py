"""April Brother BLE Gateway V4: the nRF52832 radio as its own Bluetooth scanner.

With the ab-ble-gateway-v4 firmware, the gateway's ESP32 is the normal,
connectable ESPHome Bluetooth proxy, and the nRF52832's UART is exposed raw over
the encrypted ESPHome serial proxy. This integration starts the nRF52832's
scanner, reads its stream and registers a separate, non-connectable scanner.
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.bluetooth import async_register_scanner, async_remove_scanner
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_DEVICE,
    CONF_ESPHOME_ENTRY_ID,
    CONF_PORT_NAME,
    DOMAIN,
    LEGACY_TITLE_SUFFIX,
    RADIO_NAME,
    SOURCE_MODEL,
)
from .scanner import NordicLink, NordicScanner, serial_proxy_url


@dataclass
class NordicRuntimeData:
    scanner: NordicScanner
    link: NordicLink


type NordicConfigEntry = ConfigEntry[NordicRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: NordicConfigEntry) -> bool:
    """Set up the nRF52832 scanner for one gateway."""
    esphome_entry = hass.config_entries.async_get_entry(entry.data[CONF_ESPHOME_ENTRY_ID])
    if esphome_entry is None:
        raise ConfigEntryNotReady("The gateway's ESPHome entry no longer exists")
    if esphome_entry.state is not ConfigEntryState.LOADED:
        raise ConfigEntryNotReady("The gateway's ESPHome entry is not loaded yet")
    device_info = esphome_entry.runtime_data.device_info
    if device_info is None:
        raise ConfigEntryNotReady("The gateway has not reported its device info yet")
    port_name: str = entry.data[CONF_PORT_NAME]
    if not any(proxy.name == port_name for proxy in device_info.serial_proxies):
        raise ConfigEntryNotReady(
            f"The gateway firmware has no serial proxy named {port_name!r} (ab-ble-gateway-v4 firmware not installed)"
        )

    # The ESPHome scanner uses the Bluetooth MAC; the nRF52832 scanner uses the
    # gateway's network MAC, which the stock firmware also used for it.
    source = entry.unique_id or device_info.mac_address.upper()
    name = f"{device_info.friendly_name or device_info.name} {RADIO_NAME}"
    if entry.title.endswith(LEGACY_TITLE_SUFFIX):  # Entries created by 0.1.0
        hass.config_entries.async_update_entry(
            entry, title=entry.title[: -len(LEGACY_TITLE_SUFFIX)] + f" {RADIO_NAME}"
        )
    scanner = NordicScanner(source, name, None, False)

    device_registry = dr.async_get(hass)
    # Attach the adapter to the gateway device owned by its ESPHome entry.
    device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, dr.format_mac(device_info.mac_address)), esphome_entry.entry_id
    )
    entry.async_on_unload(
        async_register_scanner(
            hass,
            scanner,
            source_domain=DOMAIN,
            source_model=SOURCE_MODEL,
            source_config_entry_id=entry.entry_id,
            source_device_id=device.id if device else None,
        )
    )
    entry.async_on_unload(scanner.async_setup())

    url = serial_proxy_url(esphome_entry.entry_id, port_name)
    if entry.data.get(CONF_DEVICE) != url:  # Entries created by 0.1.0/0.1.1
        hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_DEVICE: url})
    link = NordicLink(hass, url, scanner)
    entry.async_on_unload(link.stop)
    entry.async_create_background_task(hass, link.run(), f"{DOMAIN} stream {source}")
    entry.runtime_data = NordicRuntimeData(scanner, link)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NordicConfigEntry) -> bool:
    """Unload; nRF52832 data is not forwarded while nothing is subscribed."""
    return True


async def async_remove_entry(hass: HomeAssistant, entry: NordicConfigEntry) -> None:
    """Remove the Bluetooth adapter entry that the scanner created."""
    if entry.unique_id:
        async_remove_scanner(hass, entry.unique_id)
