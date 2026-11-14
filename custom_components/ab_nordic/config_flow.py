"""Config flow: pick an ESPHome gateway that runs the split firmware profile."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState, ConfigFlow, ConfigFlowResult

from .const import CONF_ESPHOME_ENTRY_ID, CONF_PORT_NAME, DEFAULT_PORT_NAME, DOMAIN, RADIO_NAME


class NordicConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the nRF52832 scanner."""

    VERSION = 1

    def _gateways(self) -> dict[str, tuple[str, str]]:
        """Loaded ESPHome entries exposing the nRF52832 scanner port."""
        found: dict[str, tuple[str, str]] = {}
        for entry in self.hass.config_entries.async_entries("esphome"):
            if entry.state is not ConfigEntryState.LOADED:
                continue
            info = entry.runtime_data.device_info
            if info is None or not any(p.name == DEFAULT_PORT_NAME for p in info.serial_proxies):
                continue
            if not info.mac_address or info.mac_address == info.bluetooth_mac_address:
                continue  # No distinct source address for a second scanner.
            found[entry.entry_id] = (info.friendly_name or info.name, info.mac_address.upper())
        return found

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        gateways = self._gateways()
        if not gateways:
            return self.async_abort(reason="no_gateway")
        if user_input is not None:
            entry_id = user_input[CONF_ESPHOME_ENTRY_ID]
            name, source = gateways[entry_id]
            await self.async_set_unique_id(source)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"{name} {RADIO_NAME}",
                data={CONF_ESPHOME_ENTRY_ID: entry_id, CONF_PORT_NAME: DEFAULT_PORT_NAME},
            )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ESPHOME_ENTRY_ID): vol.In(
                        {entry_id: f"{name} ({source})" for entry_id, (name, source) in gateways.items()}
                    )
                }
            ),
        )

