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
            "data": {
                "address_number": entry.data.get("address_number"),
                "street_direction": entry.data.get("street_direction"),
                "street_name": entry.data.get("street_name"),
                "street_suffix": entry.data.get("street_suffix"),
            },
        },
        "coordinator_data": coordinator.data,
    }
