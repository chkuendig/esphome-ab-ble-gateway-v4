"""Diagnostics for the Nordic scanner."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import NordicConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NordicConfigEntry
) -> dict[str, Any]:
    """Return stream counters and the scanner's view."""
    data = entry.runtime_data
    return {
        "stream": data.link.diagnostics(),
        "scanner": await data.scanner.async_diagnostics(),
    }
