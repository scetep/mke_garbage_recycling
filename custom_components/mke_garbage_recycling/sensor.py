# config/custom_components/mke_garbage_recycling/sensor.py

import logging
from datetime import date

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MkeConfigEntry
from .const import DOMAIN, SENSOR_GARBAGE, SENSOR_RECYCLING, SENSOR_CLEAN_GREEN
from .coordinator import MkeGarbageDataUpdateCoordinator
from .sources.local_calculated import CITIES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MkeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    coordinator = entry.runtime_data

    sensors_to_add = [
        MkePickupSensor(coordinator, entry, SENSOR_GARBAGE),
        MkePickupSensor(coordinator, entry, SENSOR_RECYCLING),
        MkePickupSensor(coordinator, entry, SENSOR_CLEAN_GREEN),
        MkeDaysUntilSensor(coordinator, entry, f"{SENSOR_GARBAGE} Days"),
        MkeDaysUntilSensor(coordinator, entry, f"{SENSOR_RECYCLING} Days"),
        MkeDaysUntilSensor(coordinator, entry, f"{SENSOR_CLEAN_GREEN} Days"),
    ]
    async_add_entities(sensors_to_add)
    _LOGGER.debug("Added waste collection sensors for: %s", entry.title)


class MkePickupSensor(CoordinatorEntity[MkeGarbageDataUpdateCoordinator], SensorEntity):
    """Representation of a Garbage/Recycling/Clean-Green Date Sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MkeGarbageDataUpdateCoordinator,
        entry: MkeConfigEntry,
        sensor_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self.entry = entry

        self._attr_device_class = SensorDeviceClass.DATE
        
        if sensor_type == SENSOR_GARBAGE:
            self._attr_icon = "mdi:trash-can"
        elif sensor_type == SENSOR_RECYCLING:
            self._attr_icon = "mdi:recycle"
        else:
            self._attr_icon = "mdi:leaf"

        self._attr_unique_id = f"{entry.entry_id}_{sensor_type.lower().replace(' ', '_')}"
        self._attr_name = sensor_type

        city = entry.data.get("city", "milwaukee")
        city_name = "Milwaukee" if city == "milwaukee" else CITIES.get(city, city.replace("_", " ").title())

        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": f"{city_name} Collection Data",
            "model": "Collection Schedule",
            "entry_type": "service",
        }

    @property
    def native_value(self) -> date | None:
        """Return the state of the sensor (the pickup date) from coordinator data."""
        if self.coordinator.data:
            if self._sensor_type == SENSOR_GARBAGE:
                return self.coordinator.data.get("garbage_date")
            elif self._sensor_type == SENSOR_RECYCLING:
                return self.coordinator.data.get("recycling_date")
            elif self._sensor_type == SENSOR_CLEAN_GREEN:
                return self.coordinator.data.get("clean_green_date")
        return None


class MkeDaysUntilSensor(CoordinatorEntity[MkeGarbageDataUpdateCoordinator], SensorEntity):
    """Representation of the days remaining until collection."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MkeGarbageDataUpdateCoordinator,
        entry: MkeConfigEntry,
        sensor_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self.entry = entry

        self._attr_native_unit_of_measurement = "days"
        self._attr_state_class = "measurement"
        self._attr_icon = "mdi:clock-outline"
        self._attr_unique_id = f"{entry.entry_id}_{sensor_type.lower().replace(' ', '_')}"
        self._attr_name = sensor_type

        city = entry.data.get("city", "milwaukee")
        city_name = "Milwaukee" if city == "milwaukee" else CITIES.get(city, city.replace("_", " ").title())

        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": f"{city_name} Collection Data",
            "model": "Collection Schedule",
            "entry_type": "service",
        }

    @property
    def native_value(self) -> int | None:
        """Return the number of days until the scheduled pickup."""
        if not self.coordinator.data:
            return None

        target_date = None
        if self._sensor_type.startswith(SENSOR_GARBAGE):
            target_date = self.coordinator.data.get("garbage_date")
        elif self._sensor_type.startswith(SENSOR_RECYCLING):
            target_date = self.coordinator.data.get("recycling_date")
        elif self._sensor_type.startswith(SENSOR_CLEAN_GREEN):
            target_date = self.coordinator.data.get("clean_green_date")

        if target_date:
            return (target_date - date.today()).days
        return None