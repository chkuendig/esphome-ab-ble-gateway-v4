"""April Brother BLE Gateway V4: the Nordic radio as its own Bluetooth scanner.

With the xbg-proxy-split firmware, the gateway's ESP32 is the normal,
connectable ESPHome Bluetooth proxy, and the Nordic's passive scan stream is
exposed raw over the encrypted ESPHome serial proxy. This integration reads it
and registers a separate, non-connectable Home Assistant scanner.
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.bluetooth import async_register_scanner, async_remove_scanner
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import CONF_ESPHOME_ENTRY_ID, CONF_PORT_NAME, DOMAIN, SOURCE_MODEL
from .scanner import NordicLink, NordicScanner, serial_proxy_url


@dataclass
class NordicRuntimeData:
    scanner: NordicScanner
    link: NordicLink


type NordicConfigEntry = ConfigEntry[NordicRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: NordicConfigEntry) -> bool:
    """Set up the Nordic scanner for one gateway."""
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
            f"The gateway firmware has no serial proxy named {port_name!r} (split profile not installed)"
        )

    # The ESPHome scanner uses the Bluetooth MAC; the Nordic scanner uses the
    # gateway's network MAC, which the stock firmware also used for it.
    source = entry.unique_id or device_info.mac_address.upper()
    name = f"{device_info.friendly_name or device_info.name} Nordic"
    scanner = NordicScanner(source, name, None, False)

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, dr.format_mac(device_info.mac_address))}
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

    link = NordicLink(hass, serial_proxy_url(esphome_entry.entry_id, port_name), scanner)
    entry.async_on_unload(link.stop)
    entry.async_create_background_task(hass, link.run(), f"{DOMAIN} stream {source}")
    entry.runtime_data = NordicRuntimeData(scanner, link)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NordicConfigEntry) -> bool:
    """Unload; the gateway firmware drops Nordic adverts while unsubscribed."""
    return True


async def async_remove_entry(hass: HomeAssistant, entry: NordicConfigEntry) -> None:
    """Remove the Bluetooth adapter entry that the scanner created."""
    if entry.unique_id:
        async_remove_scanner(hass, entry.unique_id)
