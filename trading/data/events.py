"""Immutable observed market-price events."""

from dataclasses import dataclass
from datetime import datetime
from math import isfinite


@dataclass(frozen=True)
class PriceEvent:
    """One observed market price at a timezone-aware timestamp."""

    timestamp: datetime
    price: float

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("PriceEvent timestamp must be timezone-aware")
        if not isfinite(self.price):
            raise ValueError("PriceEvent price must be finite")
