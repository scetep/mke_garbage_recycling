# config/custom_components/mke_garbage_recycling/sources/local_calculated.py

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict

import aiohttp

from .base import BaseWasteSource

_LOGGER = logging.getLogger(__name__)

# City Display Names
CITIES = {
    "west_allis": "West Allis",
    "wauwatosa": "Wauwatosa",
    "shorewood": "Shorewood",
    "oak_creek": "Oak Creek",
    "franklin": "Franklin",
    "greenfield": "Greenfield",
    "cudahy": "Cudahy",
    "south_milwaukee": "South Milwaukee",
    "st_francis": "St. Francis",
    "glendale": "Glendale",
    "bayside": "Bayside",
    "brown_deer": "Brown Deer",
    "fox_point": "Fox Point",
    "greendale": "Greendale",
    "hales_corners": "Hales Corners",
    "river_hills": "River Hills",
    "west_milwaukee": "West Milwaukee",
    "whitefish_bay": "Whitefish Bay",
}

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class LocalCalculatedSource(BaseWasteSource):
    """Waste schedule source calculated locally using city-specific rules and holiday shifts."""

    async def validate_input(self, session: aiohttp.ClientSession, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate input parameters locally without external network requests."""
        city = data["city"]
        city_title = CITIES.get(city, city.replace("_", " ").title())
        refuse_day = int(data["refuse_day"])
        recycling_frequency = data["recycling_frequency"]
        clean_green_date = data.get("clean_green_date", "")

        day_name = WEEKDAYS[refuse_day]
        freq_label = "Weekly Recycling" if recycling_frequency == "weekly" else f"Biweekly ({recycling_frequency.replace('_', ' ').title()})"
        
        title = f"{city_title} ({day_name}, {freq_label})"
        unique_id = f"{city}_{refuse_day}_{recycling_frequency}_{clean_green_date or 'none'}"

        return {
            "title": title,
            "unique_id": unique_id,
            "data": {
                "city": city,
                "refuse_day": refuse_day,
                "recycling_frequency": recycling_frequency,
                "clean_green_date": clean_green_date,
            }
        }

    async def fetch_schedule(self, session: aiohttp.ClientSession, data: Dict[str, Any]) -> Dict[str, date | None]:
        """Calculate garbage, recycling, and Clean & Green dates locally."""
        refuse_day = int(data["refuse_day"])
        recycling_frequency = data["recycling_frequency"]
        clean_green_str = data.get("clean_green_date", "")

        today = date.today()

        # 1. Calculate Refuse Date
        garbage_date = self._get_next_weekday(today, refuse_day)
        garbage_date = self._adjust_for_holidays(garbage_date, refuse_day)

        # 2. Calculate Recycling Date
        recycling_date = None
        if recycling_frequency == "weekly":
            recycling_date = garbage_date
        else:
            # Biweekly schedules (Route 1 / Route 2)
            # Route 1 = odd ISO week numbers, Route 2 = even ISO week numbers
            candidate_date = garbage_date
            for _ in range(4):  # Check up to 4 weeks out
                is_route_1_week = (candidate_date.isocalendar().week % 2 != 0)
                is_match = (
                    (recycling_frequency == "route_1" and is_route_1_week) or
                    (recycling_frequency == "route_2" and not is_route_1_week)
                )
                if is_match:
                    recycling_date = candidate_date
                    break
                candidate_date += timedelta(days=7)
                candidate_date = self._adjust_for_holidays(candidate_date, refuse_day)

        # 3. Calculate Clean & Green Date
        clean_green_date = None
        if clean_green_str:
            try:
                # Expecting MM-DD format, e.g. "05-18"
                month, day = map(int, clean_green_str.split("-"))
                candidate = date(today.year, month, day)
                if candidate < today:
                    candidate = date(today.year + 1, month, day)
                clean_green_date = candidate
            except Exception:
                _LOGGER.warning("Could not parse Clean & Green date string: %s", clean_green_str)

        return {
            "garbage_date": garbage_date,
            "recycling_date": recycling_date,
            "clean_green_date": clean_green_date,
        }

    def _get_next_weekday(self, start_date: date, target_weekday: int) -> date:
        """Find the next occurrence of target_weekday starting from start_date (inclusive)."""
        days_ahead = target_weekday - start_date.weekday()
        if days_ahead < 0:
            days_ahead += 7
        return start_date + timedelta(days_ahead)

    def _adjust_for_holidays(self, candidate_date: date, original_weekday: int) -> date:
        """
        Adjust collection date if a major holiday shifts the schedule.
        
        Holidays that fall on or before the pickup day in the same week shift collection by +1 day.
        """
        year = candidate_date.year
        holidays = self._get_major_holidays(year)

        # Get the Monday of candidate_date's week (to see what holidays occurred this week)
        start_of_week = candidate_date - timedelta(days=candidate_date.weekday())
        
        # Check if any holiday falls on or before original_weekday (Monday to Friday)
        for hol_date in holidays:
            # Must fall in the same week and be between Monday and the candidate date
            if start_of_week <= hol_date <= candidate_date:
                # Major holidays falling on Saturday/Sunday usually do not shift weekday routes
                if hol_date.weekday() < 5:
                    _LOGGER.debug("Adjusting pickup date %s due to holiday %s", candidate_date, hol_date)
                    return candidate_date + timedelta(days=1)
                    
        return candidate_date

    def _get_major_holidays(self, year: int) -> list[date]:
        """Calculate dates for major US holidays (including observed dates) that delay waste collection."""
        holidays = []

        def _get_observed(holiday_date: date) -> date:
            """Return the observed weekday for a holiday if it falls on a weekend."""
            if holiday_date.weekday() == 6:  # Sunday -> Observed on Monday
                return holiday_date + timedelta(days=1)
            elif holiday_date.weekday() == 5:  # Saturday -> Observed on Friday
                return holiday_date - timedelta(days=1)
            return holiday_date

        # 1. New Year's Day (Jan 1)
        holidays.append(_get_observed(date(year, 1, 1)))

        # 2. Memorial Day (Last Monday of May)
        # Start at May 31 and walk back to the last Monday
        memorial_day = date(year, 5, 31)
        while memorial_day.weekday() != 0:
            memorial_day -= timedelta(days=1)
        holidays.append(memorial_day)

        # 3. Independence Day (July 4)
        holidays.append(_get_observed(date(year, 7, 4)))

        # 4. Labor Day (First Monday of September)
        # Start at Sept 1 and walk forward to the first Monday
        labor_day = date(year, 9, 1)
        while labor_day.weekday() != 0:
            labor_day += timedelta(days=1)
        holidays.append(labor_day)

        # 5. Thanksgiving Day (Fourth Thursday of November)
        # Start at Nov 1 and find the fourth Thursday
        thanksgiving = date(year, 11, 1)
        thursdays = 0
        while thursdays < 4:
            if thanksgiving.weekday() == 3:
                thursdays += 1
                if thursdays == 4:
                    break
            thanksgiving += timedelta(days=1)
        holidays.append(thanksgiving)

        # 6. Christmas Day (Dec 25)
        holidays.append(_get_observed(date(year, 12, 25)))

        return holidays

