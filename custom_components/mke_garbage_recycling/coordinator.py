# config/custom_components/mke_garbage_recycling/coordinator.py

import logging
from datetime import date, datetime, timedelta
import re
import asyncio

import aiohttp
from bs4 import BeautifulSoup

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

# Set a default update interval (e.g., every 6 hours)
DEFAULT_SCAN_INTERVAL = timedelta(hours=6)


class MkeGarbageDataUpdateCoordinator(DataUpdateCoordinator[dict[str, date | None]]):
    """Class to manage fetching MKE garbage data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        self.hass = hass
        # Extract address details once
        self.address_number = entry.data[CONF_ADDRESS_NUMBER]
        self.street_direction = entry.data.get(CONF_STREET_DIRECTION, "") # Already uppercase/empty from flow
        self.street_name = entry.data[CONF_STREET_NAME] # Already uppercase from flow
        self.street_suffix = entry.data[CONF_STREET_SUFFIX] # Already uppercase from flow
        self.formatted_address = entry.title # Use the title set during config flow

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
            # Use asyncio.timeout for the request
            async with asyncio.timeout(15):
                response = await session.post(
                    BASE_URL, data=post_params, headers=REQUEST_HEADERS
                )
                response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
                html_content = await response.text()

        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise UpdateFailed(f"Error communicating with MKE API: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error during MKE API request")
            raise UpdateFailed(f"Unexpected error: {err}") from err

        # Check for address not found error AFTER successful request
        if "Your garbage collection schedule could not be determined." in html_content:
            # This indicates a valid connection but invalid address data persisted
            # Or the city website changed how it handles initially valid addresses
            raise UpdateFailed(f"Address not found or schedule unavailable for {self.formatted_address}")

        # Parse the HTML content
        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # Use regex on the text content for potentially better stability
            # Note: Adjust regex if the website wording changes. Uses DOTALL to match across newlines.
            # Compile regex patterns once (can be done outside function or as constants)
            garbage_pattern = re.compile(r"next\s+(?:\w+\s+)?garbage\s+collection.*?<strong>(.*?)</strong>", re.IGNORECASE | re.DOTALL)
            recycling_pattern = re.compile(r"next\s+(?:\w+\s+)?recycling\s+collection.*?<strong>(.*?)</strong>", re.IGNORECASE | re.DOTALL)
            clean_green_pattern = re.compile(r"Clean & Green Day:.*?pickup day is <b>(.*?)</b>", re.IGNORECASE | re.DOTALL)

            garbage_match = garbage_pattern.search(html_content)
            recycling_match = recycling_pattern.search(html_content)
            clean_green_match = clean_green_pattern.search(html_content)

            garbage_date_str = garbage_match.group(1).strip() if garbage_match else None
            recycling_date_str = recycling_match.group(1).strip() if recycling_match else None
            clean_green_date_str = clean_green_match.group(1).strip() if clean_green_match else None

            garbage_date = self._parse_date(garbage_date_str, "garbage")
            recycling_date = self._parse_date(recycling_date_str, "recycling")
            clean_green_date = self._parse_date(clean_green_date_str, "clean_green")

            _LOGGER.debug(
                "Successfully updated MKE data for %s. Garbage: %s, Recycling: %s, Clean & Green: %s",
                self.formatted_address, garbage_date, recycling_date, clean_green_date
            )
            return {
                "garbage_date": garbage_date,
                "recycling_date": recycling_date,
                "clean_green_date": clean_green_date,
            }

        except Exception as err:
            _LOGGER.exception("Error parsing MKE garbage data for %s", self.formatted_address)
            raise UpdateFailed(f"Error parsing data: {err}") from err


    def _parse_date(self, date_str: str | None, date_type: str) -> date | None:
        """Parse the date string from the website."""
        if not date_str:
            _LOGGER.warning("No date string found for %s pickup for address %s.", date_type, self.formatted_address)
            return None
        
        # Clean any HTML markup tags or extra whitespace
        cleaned = re.sub(r"<[^>]+>", "", date_str).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned_no_comma = cleaned.replace(",", "")

        # 1. Full Format: DayOfWeek Month Day Year (e.g. "WEDNESDAY JUNE 24 2026")
        try:
            return datetime.strptime(cleaned_no_comma, "%A %B %d %Y").date()
        except ValueError:
            pass

        # 2. Short Format: DayOfWeek Month Day (e.g. "WEDNESDAY JUNE 24") - assume current year
        try:
            return datetime.strptime(f"{cleaned_no_comma} {datetime.now().year}", "%A %B %d %Y").date()
        except ValueError:
            pass

        # 3. Month Day Year (e.g. "JUNE 24 2026" or "JUN 24 2026")
        try:
            return datetime.strptime(cleaned_no_comma, "%B %d %Y").date()
        except ValueError:
            pass
        try:
            return datetime.strptime(cleaned_no_comma, "%b %d %Y").date()
        except ValueError:
            pass

        # 4. Month Day (e.g. "JUNE 24" or "JUN 24" or "May 18") - assume current year
        try:
            return datetime.strptime(f"{cleaned_no_comma} {datetime.now().year}", "%B %d %Y").date()
        except ValueError:
            pass
        try:
            return datetime.strptime(f"{cleaned_no_comma} {datetime.now().year}", "%b %d %Y").date()
        except ValueError:
            pass

        # 5. Weekday Format: e.g. "WEDNESDAY" - calculate next occurrence of that weekday
        weekdays = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
        if cleaned_no_comma.upper() in weekdays:
            try:
                weekday_idx = weekdays.index(cleaned_no_comma.upper())
                today = date.today()
                days_ahead = weekday_idx - today.weekday()
                if days_ahead < 0:
                    days_ahead += 7
                return today + timedelta(days_ahead)
            except ValueError:
                pass

        _LOGGER.error(
            "Could not parse %s date string: '%s' for address %s. Check expected format.",
            date_type, date_str, self.formatted_address
        )
        return None