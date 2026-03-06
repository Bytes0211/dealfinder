"""Data access layer for Deal Finder.

This module provides repository patterns for database operations
and data management utilities.
"""

from dealfinder.data.repository import (
    DealRepository,
    DealSourceRepository,
    NotificationRepository,
    PriceEstimateRepository,
    UserRepository,
)

__all__ = [
    "DealRepository",
    "DealSourceRepository",
    "NotificationRepository",
    "PriceEstimateRepository",
    "UserRepository",
]
