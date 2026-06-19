# config/custom_components/mke_garbage_recycling/sources/milwaukee.py

import logging
import asyncio
from datetime import date, datetime, timedelta
import re
from typing import Any, Dict

import aiohttp
from bs4 import BeautifulSoup

from .base import BaseWasteSource, CannotConnectError, AddressNotFoundError
from ..const import (
    CONF_ADDRESS_NUMBER,
    CONF_STREET_DIRECTION,
    CONF_STREET_NAME,
    CONF_STREET_SUFFIX,
    BASE_URL,
    REQUEST_PARAMS,
    REQUEST_HEADERS,
)

_LOGGER = logging.getLogger(__name__)


class MilwaukeeSource(BaseWasteSource):
    """Waste schedule source for the City of Milwaukee."""

    async def validate_input(self, session: aiohttp.ClientSession, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate address config against City of Milwaukee DPW."""
        address_number = data[CONF_ADDRESS_NUMBER]
        street_direction = (data.get(CONF_STREET_DIRECTION, "") or "").upper()
        street_name = data[CONF_STREET_NAME].upper()
        street_suffix = (data.get(CONF_STREET_SUFFIX, "") or "").upper()

        post_params = {
            "laddr": address_number,
            "sdir": street_direction,
            "sname": street_name,
            "stype": street_suffix,
            "embed": REQUEST_PARAMS["embed"],
            "Submit": "Submit",
        }

        formatted_address = f"{address_number} {street_direction} {street_name} {street_suffix}".strip().replace("  ", " ")
        _LOGGER.debug("Validating Milwaukee address: %s", formatted_address)

        try:
            async with session.post(
                BASE_URL, data=post_params, headers=REQUEST_HEADERS, timeout=10
            ) as response:
                response.raise_for_status()
                html_content = await response.text()

                if "Your garbage collection schedule could not be determined." in html_content:
                    _LOGGER.warning("Validation failed: Address not found for %s", formatted_address)
                    raise AddressNotFoundError

                _LOGGER.debug("Validation successful for %s", formatted_address)
                
                unique_id = f"milwaukee_{address_number}_{street_direction}_{street_name}_{street_suffix}"
                return {
                    "title": f"Milwaukee ({formatted_address})",
                    "unique_id": unique_id,
                    "data": {
                        "city": "milwaukee",
                        CONF_ADDRESS_NUMBER: address_number,
                        CONF_STREET_DIRECTION: street_direction,
                        CONF_STREET_NAME: street_name,
                        CONF_STREET_SUFFIX: street_suffix,
                    }
                }

        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Validation failed: Cannot connect to MKE website - %s", err)
            raise CannotConnectError from err
        except AddressNotFoundError:
            raise
        except Exception as err:
            _LOGGER.exception("Validation failed: Unexpected error occurred")
            raise CannotConnectError(f"Unexpected error: {err}") from err

    async def fetch_schedule(self, session: aiohttp.ClientSession, data: Dict[str, Any]) -> Dict[str, date | None]:
        """Fetch schedule from City of Milwaukee DPW website."""
        address_number = data[CONF_ADDRESS_NUMBER]
        street_direction = data.get(CONF_STREET_DIRECTION, "")
        street_name = data[CONF_STREET_NAME]
        street_suffix = data.get(CONF_STREET_SUFFIX, "")
        formatted_address = f"{address_number} {street_direction} {street_name} {street_suffix}".strip().replace("  ", " ")

        post_params = {
            "laddr": address_number,
            "sdir": street_direction,
            "sname": street_name,
            "stype": street_suffix,
            "embed": REQUEST_PARAMS["embed"],
            "Submit": "Submit",
        }

        try:
            async with asyncio.timeout(15):
                response = await session.post(
                    BASE_URL, data=post_params, headers=REQUEST_HEADERS
                )
                response.raise_for_status()
                html_content = await response.text()

        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnectError(f"Error communicating with MKE API: {err}") from err
        except Exception as err:
            raise CannotConnectError(f"Unexpected error: {err}") from err

        if "Your garbage collection schedule could not be determined." in html_content:
            raise AddressNotFoundError(f"Address not found or schedule unavailable for {formatted_address}")

        try:
            garbage_pattern = re.compile(r"next\s+(?:\w+\s+)?garbage\s+collection.*?<strong>(.*?)</strong>", re.IGNORECASE | re.DOTALL)
            recycling_pattern = re.compile(r"next\s+(?:\w+\s+)?recycling\s+collection.*?<strong>(.*?)</strong>", re.IGNORECASE | re.DOTALL)
            clean_green_pattern = re.compile(r"Clean & Green Day:.*?pickup day is <b>(.*?)</b>", re.IGNORECASE | re.DOTALL)

            garbage_match = garbage_pattern.search(html_content)
            recycling_match = recycling_pattern.search(html_content)
            clean_green_match = clean_green_pattern.search(html_content)

            garbage_date_str = garbage_match.group(1).strip() if garbage_match else None
            recycling_date_str = recycling_match.group(1).strip() if recycling_match else None
            clean_green_date_str = clean_green_match.group(1).strip() if clean_green_match else None

            garbage_date = self._parse_date(garbage_date_str, "garbage", formatted_address)
            recycling_date = self._parse_date(recycling_date_str, "recycling", formatted_address)
            clean_green_date = self._parse_date(clean_green_date_str, "clean_green", formatted_address)

            return {
                "garbage_date": garbage_date,
                "recycling_date": recycling_date,
                "clean_green_date": clean_green_date,
            }

        except Exception as err:
            _LOGGER.exception("Error parsing MKE garbage data for %s", formatted_address)
            raise CannotConnectError(f"Error parsing data: {err}") from err

    def _parse_date(self, date_str: str | None, date_type: str, formatted_address: str) -> date | None:
        """Parse the date string from the website."""
        if not date_str:
            _LOGGER.warning("No date string found for %s pickup for address %s.", date_type, formatted_address)
            return None
        
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
            date_type, date_str, formatted_address
        )
        return None
