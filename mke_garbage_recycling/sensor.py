# config/custom_components/mke_garbage_recycling/sensor.py

import logging
from datetime import date

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSOR_GARBAGE, SENSOR_RECYCLING
# Import the coordinator class
from .coordinator import MkeGarbageDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    # Create the coordinator instance
    coordinator = MkeGarbageDataUpdateCoordinator(hass, entry)

    # Fetch initial data so we have data when entities subscribe
    # Returns the data fetched, or raises an exception handled by component setup logic
    await coordinator.async_config_entry_first_refresh()

    # Optional: Store coordinator instance if other platforms need it
    # hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    sensors_to_add = [
        MkePickupSensor(coordinator, entry, SENSOR_GARBAGE),
        MkePickupSensor(coordinator, entry, SENSOR_RECYCLING),
    ]
    async_add_entities(sensors_to_add)
    _LOGGER.debug("Added MKE Garbage sensors for address: %s", entry.title)


class MkePickupSensor(CoordinatorEntity[MkeGarbageDataUpdateCoordinator], SensorEntity):
    """Representation of a MKE Garbage/Recycling Sensor."""

    _attr_has_entity_name = True # Use device name + entity name convention

    def __init__(
        self,
        coordinator: MkeGarbageDataUpdateCoordinator,
        entry: ConfigEntry,
        sensor_type: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator) # Initialize CoordinatorEntity
        self._sensor_type = sensor_type
        self.entry = entry # Store entry for easy access to config data if needed

        # Set basic attributes
        self._attr_device_class = SensorDeviceClass.DATE
        self._attr_icon = "mdi:trash-can" if sensor_type == SENSOR_GARBAGE else "mdi:recycle"

        # Set unique ID based on config entry ID and sensor type
        self._attr_unique_id = f"{entry.entry_id}_{sensor_type.lower().replace(' ', '_')}"

        # Set entity name (will be combined with device name)
        self._attr_name = sensor_type # e.g., "Garbage Pickup"

        # Link sensor to device representing the address
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title, # Device name is the address (e.g., "123 N MAIN ST")
            "manufacturer": "City of Milwaukee Data",
            "model": "Collection Schedule",
            "entry_type": "service", # Recommended for integrations pulling data
            # "configuration_url": BASE_URL, # Optional: Link to the base website
        }

    @property
    def native_value(self) -> date | None:
        """Return the state of the sensor (the pickup date) from coordinator data."""
        # Data is managed by CoordinatorEntity, access via self.coordinator.data
        if self.coordinator.data:
            if self._sensor_type == SENSOR_GARBAGE:
                return self.coordinator.data.get("garbage_date")
            elif self._sensor_type == SENSOR_RECYCLING:
                return self.coordinator.data.get("recycling_date")
        # Return None if coordinator data is unavailable or key is missing
        return None

    # The 'available' property is handled by CoordinatorEntity based on
    # the coordinator's last update success. You usually don't need to override it.
    # @property
    # def available(self) -> bool:
    #     """Return if entity is available."""
    #     return super().available and self.coordinator.data is not None

    # Add extra state attributes if needed (e.g., last successful update time)
    # @property
    # def extra_state_attributes(self) -> dict[str, Any] | None:
    #     """Return additional state attributes."""
    #     attrs = {}
    #     if self.coordinator.last_update_success:
    #          attrs["last_successful_update"] = self.coordinator.last_update_success_time
    #     # Add other attributes if desired
    #     return attrs