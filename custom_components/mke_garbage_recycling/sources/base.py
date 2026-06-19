# config/custom_components/mke_garbage_recycling/sources/base.py

import logging
from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Dict

import aiohttp

_LOGGER = logging.getLogger(__name__)


class CannotConnectError(Exception):
    """Exception raised when unable to connect to the city's schedule website."""
    pass


class AddressNotFoundError(Exception):
    """Exception raised when the address details cannot be validated or found."""
    pass


class BaseWasteSource(ABC):
    """Abstract base class representing a city-specific waste collection schedule provider."""

    @abstractmethod
    async def validate_input(self, session: aiohttp.ClientSession, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate the user configuration input.
        
        Should raise CannotConnectError or AddressNotFoundError if validation fails.
        Should return a dictionary containing:
        - "title": The formatted friendly title for the integration (e.g. the formatted address).
        - "unique_id": A string uniquely identifying this configuration to prevent duplicates.
        - "data": The sanitized configuration data dictionary to be saved in the config entry.
        """
        pass

    @abstractmethod
    async def fetch_schedule(self, session: aiohttp.ClientSession, data: Dict[str, Any]) -> Dict[str, date | None]:
        """
        Fetch and parse the upcoming pickup schedule.
        
        Should return a dictionary with keys:
        - "garbage_date": date | None
        - "recycling_date": date | None
        - "clean_green_date": date | None
        """
        pass
