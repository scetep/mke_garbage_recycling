# config/custom_components/mke_garbage_recycling/config_flow.py

import logging
from typing import Any, Dict

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_ADDRESS_NUMBER,
    CONF_STREET_DIRECTION,
    CONF_STREET_NAME,
    CONF_STREET_SUFFIX,
)
from .sources.base import CannotConnectError, AddressNotFoundError
from .sources.milwaukee import MilwaukeeSource
from .sources.local_calculated import LocalCalculatedSource, CITIES

_LOGGER = logging.getLogger(__name__)


class MkeGarbageRecyclingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a multi-step config flow for Milwaukee County Waste Collection."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self) -> None:
        """Initialize flow."""
        self.selected_city: str | None = None

    async def async_step_user(self, user_input: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Step 1: Select City."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            self.selected_city = user_input["city"]
            if self.selected_city == "milwaukee":
                return await self.async_step_milwaukee()
            else:
                return await self.async_step_local_calculated()

        # Build list of city choices from local_calculated + milwaukee
        city_choices = {"milwaukee": "Milwaukee (City)"}
        city_choices.update({k: f"{v} (Suburbs)" for k, v in CITIES.items()})

        schema = vol.Schema({
            vol.Required("city", default="milwaukee"): vol.In(city_choices)
        })

        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    async def async_step_milwaukee(self, user_input: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Step 2 (Milwaukee): Enter address details."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            # Set default values for optional fields
            user_input.setdefault(CONF_STREET_DIRECTION, "")
            user_input.setdefault(CONF_STREET_SUFFIX, "")

            try:
                session = async_get_clientsession(self.hass)
                source = MilwaukeeSource()
                validated = await source.validate_input(session, user_input)
                
                # Check unique ID to avoid duplicates
                await self.async_set_unique_id(validated["unique_id"])
                self._abort_if_unique_id_configured()

                _LOGGER.info("Creating config entry for Milwaukee address: %s", validated["title"])
                return self.async_create_entry(
                    title=validated["title"],
                    data=validated["data"]
                )

            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except AddressNotFoundError:
                errors["base"] = "address_not_found"
            except config_entries.AbortFlow as err:
                 raise err
            except Exception:
                _LOGGER.exception("Unexpected exception during Milwaukee config flow validation")
                errors["base"] = "unknown"

        # Show Milwaukee form
        schema = vol.Schema({
            vol.Required(CONF_ADDRESS_NUMBER): cv.string,
            vol.Optional(CONF_STREET_DIRECTION, default=""): vol.In(["N", "S", "E", "W", ""]),
            vol.Required(CONF_STREET_NAME): cv.string,
            vol.Optional(CONF_STREET_SUFFIX, default=""): vol.In(["", "AV", "BL", "CR", "CT", "DR", "LA", "PK", "PL", "RD", "SQ", "ST", "SV", "TR", "WA"]),
        })

        return self.async_show_form(
            step_id="milwaukee", data_schema=schema, errors=errors
        )

    async def async_step_local_calculated(self, user_input: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Step 2 (Other Suburbs): Configure collection schedule details."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            # Include the city selected in Step 1
            user_input["city"] = self.selected_city
            
            try:
                session = async_get_clientsession(self.hass)
                source = LocalCalculatedSource()
                validated = await source.validate_input(session, user_input)

                await self.async_set_unique_id(validated["unique_id"])
                self._abort_if_unique_id_configured()

                _LOGGER.info("Creating config entry for calculated city: %s", validated["title"])
                return self.async_create_entry(
                    title=validated["title"],
                    data=validated["data"]
                )
                
            except config_entries.AbortFlow as err:
                 raise err
            except Exception:
                _LOGGER.exception("Unexpected exception during calculated config flow validation")
                errors["base"] = "unknown"

        # Weekdays choice
        day_choices = {
            "0": "Monday",
            "1": "Tuesday",
            "2": "Wednesday",
            "3": "Thursday",
            "4": "Friday",
        }

        # Recycling frequency choices
        freq_choices = {
            "weekly": "Every Week",
            "route_1": "Biweekly - Route 1 / Odd Weeks",
            "route_2": "Biweekly - Route 2 / Even Weeks",
        }

        schema = vol.Schema({
            vol.Required("refuse_day", default="1"): vol.In(day_choices),
            vol.Required("recycling_frequency", default="weekly"): vol.In(freq_choices),
            vol.Optional("clean_green_date", default=""): cv.string,
        })

        return self.async_show_form(
            step_id="local_calculated", data_schema=schema, errors=errors
        )