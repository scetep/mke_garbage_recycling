import logging
from datetime import date, datetime, timedelta # Added datetime and timedelta

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSOR_GARBAGE, SENSOR_RECYCLING
from .coordinator import MkeGarbageDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    coordinator = MkeGarbageDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    sensors_to_add = [
        MkePickupSensor(coordinator, entry, SENSOR_GARBAGE),
        MkePickupSensor(coordinator, entry, SENSOR_RECYCLING),
    ]
    async_add_entities(sensors_to_add)
    _LOGGER.debug("Added MKE Garbage sensors for address: %s", entry.title)


class MkePickupSensor(CoordinatorEntity[MkeGarbageDataUpdateCoordinator], SensorEntity):
    """Representation of a MKE Garbage/Recycling Sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MkeGarbageDataUpdateCoordinator,
        entry: ConfigEntry,
        sensor_type: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self.entry = entry
        
        # We set the device class to DATE, so HA expects a date object
        self._attr_device_class = SensorDeviceClass.DATE
        
        # Base icon (dynamic logic handled in property below)
        self._base_icon = "mdi:trash-can" if sensor_type == SENSOR_GARBAGE else "mdi:recycle"

        self._attr_unique_id = f"{entry.entry_id}_{sensor_type.lower().replace(' ', '_')}"
        self._attr_name = sensor_type

        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "City of Milwaukee Data",
            "model": "Collection Schedule",
            "entry_type": "service",
        }

    @property
    def native_value(self) -> date | None:
        """Return the state of the sensor (the pickup date)."""
        if not self.coordinator.data:
            return None
            
        # Get raw value
        key = "garbage_date" if self._sensor_type == SENSOR_GARBAGE else "recycling_date"
        raw_value = self.coordinator.data.get(key)

        # IMPROVEMENT: Ensure we return a real date object
        if isinstance(raw_value, date):
            return raw_value
        elif isinstance(raw_value, str):
            try:
                # Attempt to parse ISO format if it's a string
                return date.fromisoformat(raw_value)
            except ValueError:
                # If API returns weird text, log it and return None
                _LOGGER.warning("Could not parse date string: %s", raw_value)
                return None
        return None

    @property
    def icon(self) -> str:
        """Dynamic icon: Change if pickup is today."""
        pickup_date = self.native_value
        if pickup_date and pickup_date == date.today():
            return "mdi:truck-check" # Icon showing the truck is here/done
        return self._base_icon

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return additional attributes."""
        attrs = {}
        pickup_date = self.native_value
        
        if pickup_date:
            # IMPROVEMENT: Calculate days until pickup
            delta = pickup_date - date.today()
            attrs["days_until"] = delta.days
            
            # Add a human-readable text description
            if delta.days == 0:
                attrs["human_status"] = "Today"
            elif delta.days == 1:
                attrs["human_status"] = "Tomorrow"
            else:
                attrs["human_status"] = f"In {delta.days} days"

        return attrs
