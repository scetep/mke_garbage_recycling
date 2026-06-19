# config/custom_components/mke_garbage_recycling/coordinator.py

import logging
from datetime import date, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .sources.base import BaseWasteSource, CannotConnectError, AddressNotFoundError
from .sources.milwaukee import MilwaukeeSource
from .sources.local_calculated import LocalCalculatedSource

_LOGGER = logging.getLogger(__name__)

# Set a default update interval (e.g., every 6 hours)
DEFAULT_SCAN_INTERVAL = timedelta(hours=6)


class MkeGarbageDataUpdateCoordinator(DataUpdateCoordinator[dict[str, date | None]]):
    """Class to manage fetching garbage collection data dynamically from different sources."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        self.hass = hass
        self.formatted_address = entry.title

        # Determine which city / strategy to load
        # Default to 'milwaukee' for backwards compatibility with existing configuration entries
        self.city = entry.data.get("city", "milwaukee")
        
        if self.city == "milwaukee":
            self.source: BaseWasteSource = MilwaukeeSource()
        else:
            self.source = LocalCalculatedSource()

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({self.formatted_address})",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, date | None]:
        """Fetch data from the selected strategy source."""
        _LOGGER.debug("Fetching waste collection data for %s using strategy %s", self.formatted_address, self.city)
        session = async_get_clientsession(self.hass)

        try:
            # Fetch the schedule dynamically from the strategy provider
            schedule = await self.source.fetch_schedule(session, self.entry.data)
            
            _LOGGER.debug(
                "Successfully updated data for %s. Garbage: %s, Recycling: %s, Clean & Green: %s",
                self.formatted_address,
                schedule.get("garbage_date"),
                schedule.get("recycling_date"),
                schedule.get("clean_green_date"),
            )
            return {
                "garbage_date": schedule.get("garbage_date"),
                "recycling_date": schedule.get("recycling_date"),
                "clean_green_date": schedule.get("clean_green_date"),
            }

        except (CannotConnectError, ConnectionError) as err:
            raise UpdateFailed(f"Connection error while updating data: {err}") from err
        except AddressNotFoundError as err:
            raise UpdateFailed(f"Address validation error during update: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error updating waste collection schedule")
            raise UpdateFailed(f"Unexpected error: {err}") from err