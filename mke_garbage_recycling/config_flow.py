# config/custom_components/mke_garbage_recycling/config_flow.py

import logging
import asyncio
from typing import Any, Dict, Optional

import voluptuous as vol
import aiohttp
from bs4 import BeautifulSoup

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

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

# Define validation schema for user input
# Making direction optional with specific choices
DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ADDRESS_NUMBER): cv.string,
        vol.Optional(CONF_STREET_DIRECTION): vol.In(['N', 'S', 'E', 'W', '']),
        vol.Required(CONF_STREET_NAME): cv.string,
        #vol.Required(CONF_STREET_SUFFIX): cv.string,
        vol.Required(CONF_STREET_SUFFIX): vol.In(['AV', 'BL', 'CR', 'CT', 'DR', 'LA', 'PK', 'PL', 'RD', 'SQ', 'ST', 'SV', 'TR', 'WA' ]),
    }
)

# Define custom exceptions for validation feedback
class AddressNotFoundError(Exception):
    """Exception raised when the address is not found on the MKE website."""
    pass

class CannotConnectError(Exception):
    """Exception raised when unable to connect to the MKE website."""
    pass


async def validate_input(hass, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate the user input allows us to connect and find the address.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    session = async_get_clientsession(hass)

    address_number = data[CONF_ADDRESS_NUMBER]
    # Handle optional direction, ensure uppercase if present, default to empty string
    street_direction = data.get(CONF_STREET_DIRECTION, "").upper()
    street_name = data[CONF_STREET_NAME].upper()
    street_suffix = data[CONF_STREET_SUFFIX].upper()

    post_params = {
        "laddr": address_number,
        "sdir": street_direction,
        "sname": street_name,
        "stype": street_suffix,
        "embed": REQUEST_PARAMS["embed"],
        "Submit": "Submit",
    }

    formatted_address = f"{address_number} {street_direction} {street_name} {street_suffix}".strip().replace("  ", " ")
    _LOGGER.debug("Validating address: %s", formatted_address)

    try:
        async with session.post(
            BASE_URL, data=post_params, headers=REQUEST_HEADERS, timeout=10
        ) as response:
            response.raise_for_status()  # Raise exception for non-200 status codes
            html_content = await response.text()

            # Check specifically for the "not found" message
            if "Your garbage collection schedule could not be determined." in html_content:
                _LOGGER.warning("Validation failed: Address not found for %s", formatted_address)
                raise AddressNotFoundError

            # Optional: A more robust check could try parsing here, but checking
            # for the error message is usually sufficient for validation.

            _LOGGER.debug("Validation successful for %s", formatted_address)
            # Return validated and formatted data (like uppercase streets)
            return {
                CONF_ADDRESS_NUMBER: address_number,
                CONF_STREET_DIRECTION: street_direction, # Keep uppercase or empty
                CONF_STREET_NAME: street_name,
                CONF_STREET_SUFFIX: street_suffix,
                "formatted_address": formatted_address # Store for title
            }

    except (aiohttp.ClientError, asyncio.TimeoutError) as err:
        _LOGGER.error("Validation failed: Cannot connect to MKE website - %s", err)
        raise CannotConnectError from err
    except AddressNotFoundError:
        # Re-raise the specific error
        raise
    except Exception as err:
        _LOGGER.exception("Validation failed: Unexpected error occurred")
        raise CannotConnectError(f"Unexpected error: {err}") from err # Treat other errors as connection issues for simplicity


class MkeGarbageRecyclingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Milwaukee Garbage and Recycling."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Handle the initial step."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            # Add empty string for direction if not provided by user (handles Optional field)
            user_input.setdefault(CONF_STREET_DIRECTION, "")

            try:
                # Validate the user input with the external service
                validated_data = await validate_input(self.hass, user_input)
                formatted_address = validated_data["formatted_address"] # Get from validation result

                # Create a unique ID based on the core address components to prevent duplicates
                unique_id = f"{validated_data[CONF_ADDRESS_NUMBER]}_{validated_data[CONF_STREET_DIRECTION]}_{validated_data[CONF_STREET_NAME]}_{validated_data[CONF_STREET_SUFFIX]}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                _LOGGER.info("Creating config entry for address: %s", formatted_address)
                # Pass the original user input (or slightly cleaned up) to be stored
                # Don't store the temporary 'formatted_address' key in the entry's data
                entry_data = {
                    CONF_ADDRESS_NUMBER: validated_data[CONF_ADDRESS_NUMBER],
                    CONF_STREET_DIRECTION: validated_data[CONF_STREET_DIRECTION],
                    CONF_STREET_NAME: validated_data[CONF_STREET_NAME],
                    CONF_STREET_SUFFIX: validated_data[CONF_STREET_SUFFIX],
                }
                return self.async_create_entry(title=formatted_address, data=entry_data)

            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except AddressNotFoundError:
                errors["base"] = "address_not_found"
            except config_entries.AbortFlow as err:
                 # AbortFlow is raised by _abort_if_unique_id_configured()
                 # We just re-raise it to stop the flow correctly
                 raise err
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception during config flow validation")
                errors["base"] = "unknown"

        # If user_input is None (first show) or validation failed, show the form
        # Pre-fill the form with previous input if validation failed
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors,
            description_placeholders={"url": BASE_URL} # Optional: Can add placeholders to strings.yaml
        )