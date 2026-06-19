# config/custom_components/mke_garbage_recycling/diagnostics.py

from typing import Any

from homeassistant.core import HomeAssistant

from . import MkeConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MkeConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    return {
        "config_entry": {
            "title": entry.title,
            "data": dict(entry.data),
        },
        "coordinator_data": coordinator.data,
    }
