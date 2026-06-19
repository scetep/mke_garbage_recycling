# config/custom_components/mke_garbage_recycling/calendar.py

import logging
from datetime import date, datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MkeConfigEntry
from .const import DOMAIN
from .coordinator import MkeGarbageDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MkeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up calendar entries from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities([MkeCollectionCalendar(coordinator, entry)])


class MkeCollectionCalendar(CalendarEntity):
    """Representation of the Milwaukee Collection Calendar."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MkeGarbageDataUpdateCoordinator,
        entry: MkeConfigEntry,
    ) -> None:
        """Initialize the calendar."""
        self.coordinator = coordinator
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_calendar"
        self._attr_name = "Collection Calendar"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "City of Milwaukee Data",
            "model": "Collection Schedule",
            "entry_type": "service",
        }

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        events = self._get_events_list()
        if not events:
            return None
        # Sort events by start date and return the first one starting today or in the future
        today = date.today()
        upcoming = [e for e in events if e.start >= today]
        if not upcoming:
            return None
        upcoming.sort(key=lambda x: x.start)
        return upcoming[0]

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        # start_date and end_date are timezone-aware datetimes
        start_d = start_date.date()
        end_d = end_date.date()

        events = self._get_events_list()
        # Filter events within the range [start_d, end_d]
        return [e for e in events if start_d <= e.start <= end_d]

    def _get_events_list(self) -> list[CalendarEvent]:
        """Generate the list of calendar events from coordinator data."""
        events = []
        if not self.coordinator.data:
            return events

        # Extract dates
        garbage_date = self.coordinator.data.get("garbage_date")
        recycling_date = self.coordinator.data.get("recycling_date")
        clean_green_date = self.coordinator.data.get("clean_green_date")

        if garbage_date:
            events.append(
                CalendarEvent(
                    summary="Garbage Pickup",
                    start=garbage_date,
                    end=garbage_date + timedelta(days=1),
                    description="Scheduled garbage collection by City of Milwaukee.",
                )
            )

        if recycling_date:
            events.append(
                CalendarEvent(
                    summary="Recycling Pickup",
                    start=recycling_date,
                    end=recycling_date + timedelta(days=1),
                    description="Scheduled recycling collection by City of Milwaukee.",
                )
            )

        if clean_green_date:
            events.append(
                CalendarEvent(
                    summary="Clean & Green Pickup",
                    start=clean_green_date,
                    end=clean_green_date + timedelta(days=1),
                    description="Clean & Green neighborhood cleanup day.",
                )
            )

        return events
