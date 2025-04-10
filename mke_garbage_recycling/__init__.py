# config/custom_components/mke_garbage_recycling/__init__.py

"""The Milwaukee Garbage and Recycling integration."""
import logging

from homeassistant.config_entries import ConfigEntry # Required if using config_flow
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform

from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Milwaukee Garbage and Recycling component from configuration.yaml."""
    # Ensure the domain is present in the config, even if empty
    hass.data.setdefault(DOMAIN, {})
    _LOGGER.debug("Setting up MKE Garbage from YAML: %s", config.get(DOMAIN))
    # We don't have configuration entries based on YAML alone in this basic setup
    # The platform setup will handle the YAML config discovery
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Milwaukee Garbage and Recycling from a config entry."""
    # This function is needed if you use config_flow.py
    # Store the config entry data for platforms to access
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry.data 
    _LOGGER.debug("Setting up entry %s for address: %s", entry.entry_id, entry.title)

    # Forward the setup to the sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading entry %s for address: %s", entry.entry_id, entry.title)
    # This function is needed if you use config_flow.py
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok