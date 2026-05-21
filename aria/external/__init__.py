"""External API clients for DOSM, news, and Malaysia calendar data."""

from aria.external.dosm import DOSMClient, DOSMAPIError
from aria.external.news_api import NewsAPIClient
from aria.external.malaysia_calendar import MalaysiaCalendarClient

__all__ = [
    "DOSMClient",
    "DOSMAPIError",
    "NewsAPIClient",
    "MalaysiaCalendarClient",
]
