# config/custom_components/mke_garbage_recycling/__init__.py

"""The Milwaukee Garbage and Recycling integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import MkeGarbageDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

MkeConfigEntry = ConfigEntry[MkeGarbageDataUpdateCoordinator]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Milwaukee Garbage and Recycling component."""
    # YAML configuration is not supported, configuration is done via UI config flow.
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MkeConfigEntry) -> bool:
    """Set up Milwaukee Garbage and Recycling from a config entry."""
    _LOGGER.debug("Setting up entry %s for address: %s", entry.entry_id, entry.title)

    # Initialize the data update coordinator
    coordinator = MkeGarbageDataUpdateCoordinator(hass, entry)

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator instance in runtime_data
    entry.runtime_data = coordinator

    # Forward the setup to the sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MkeConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading entry %s for address: %s", entry.entry_id, entry.title)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)