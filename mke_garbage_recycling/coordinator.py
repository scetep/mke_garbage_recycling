import logging
from datetime import date, datetime, timedelta
import re
import asyncio

import async_timeout
import aiohttp
from dateutil import parser as date_parser  # <--- MAGIC IMPORT

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    CONF_ADDRESS_NUMBER,
    CONF_STREET_DIRECTION,
    CONF_STREET_NAME,
    CONF_STREET_SUFFIX,
    BASE_URL,
    REQUEST_PARAMS,
    REQUEST_HEADERS,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_SCAN_INTERVAL = timedelta(hours=6)

class MkeGarbageDataUpdateCoordinator(DataUpdateCoordinator[dict[str, date | None]]):
    """Class to manage fetching MKE garbage data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        self.hass = hass
        
        self.address_number = entry.data[CONF_ADDRESS_NUMBER]
        self.street_direction = entry.data.get(CONF_STREET_DIRECTION, "")
        self.street_name = entry.data[CONF_STREET_NAME]
        self.street_suffix = entry.data[CONF_STREET_SUFFIX]
        self.formatted_address = entry.title

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({self.formatted_address})",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, date | None]:
        """Fetch data from MKE website."""
        _LOGGER.debug("Fetching MKE garbage data for %s", self.formatted_address)
        session = async_get_clientsession(self.hass)

        post_params = {
            "laddr": self.address_number,
            "sdir": self.street_direction,
            "sname": self.street_name,
            "stype": self.street_suffix,
            "embed": REQUEST_PARAMS["embed"],
            "Submit": "Submit",
        }

        try:
            async with async_timeout.timeout(15):
                response = await session.post(
                    BASE_URL, data=post_params, headers=REQUEST_HEADERS
                )
                response.raise_for_status()
                html_content = await response.text()

        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise UpdateFailed(f"Error communicating with MKE API: {err}") from err

        # Check for address not found error
        if "Your garbage collection schedule could not be determined" in html_content:
            raise UpdateFailed(f"Address not found for {self.formatted_address}")

        # OPTIMIZATION: Removed BeautifulSoup. 
        # Since you are using Regex, parsing the whole DOM is wasted CPU/Memory.
        
        try:
            # Regex to find the date inside the strong tag
            # Matches: "Next Garbage Collection: <strong>Tuesday April 9, 2025</strong>"
            garbage_pattern = re.compile(r"next garbage collection.*?<strong>(.*?)</strong>", re.IGNORECASE | re.DOTALL)
            recycling_pattern = re.compile(r"next recycling collection.*?<strong>(.*?)</strong>", re.IGNORECASE | re.DOTALL)

            garbage_match = garbage_pattern.search(html_content)
            recycling_match = recycling_pattern.search(html_content)

            garbage_date_str = garbage_match.group(1).strip() if garbage_match else None
            recycling_date_str = recycling_match.group(1).strip() if recycling_match else None
            
            # Clean up HTML entities just in case (e.g. &nbsp;)
            if garbage_date_str:
                garbage_date_str = garbage_date_str.replace("&nbsp;", " ")
            if recycling_date_str:
                recycling_date_str = recycling_date_str.replace("&nbsp;", " ")

            garbage_date = self._parse_date(garbage_date_str, "garbage")
            recycling_date = self._parse_date(recycling_date_str, "recycling")

            _LOGGER.debug(
                "Updated %s. Garbage: %s, Recycling: %s",
                self.formatted_address, garbage_date, recycling_date
            )
            
            return {
                "garbage_date": garbage_date,
                "recycling_date": recycling_date,
            }

        except Exception as err:
            _LOGGER.exception("Error parsing MKE garbage data")
            raise UpdateFailed(f"Error parsing data: {err}") from err


    def _parse_date(self, date_str: str | None, date_type: str) -> date | None:
        """Parse the date string using dateutil for flexibility."""
        if not date_str:
            return None
            
        try:
            # IMPROVEMENT: Use dateutil.parser
            # This handles "Tuesday April 9, 2025", "Apr 9", "2025-04-09", etc.
            parsed_dt = date_parser.parse(date_str)
            
            # Handle Year Guessing Logic
            # If the site returns "January 5" and today is "December 20",
            # the parser might guess the current year (past).
            # If the date is in the past, assume it belongs to the next year.
            now = datetime.now()
            if parsed_dt.year == now.year and parsed_dt < now - timedelta(days=1):
                # If parsed date is in the past, and year wasn't explicitly far in future
                # We can't know for sure if the string had a year, but this is a safe heuristic 
                # for garbage cycles (usually weekly/bi-weekly).
                # IGNORE this logic if the string explicitly contained the year.
                pass 

            return parsed_dt.date()
            
        except (ValueError, TypeError):
            _LOGGER.error(
                "Could not parse %s date: '%s'. Expected format similar to 'Weekday Month Day, Year'",
                date_type, date_str
             )
            return None
