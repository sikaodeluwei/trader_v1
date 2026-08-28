"""Strict isolated high/low definitions and incremental detection."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from .candles import Candle


class IsolatedPointKind(Enum):
    """The price extreme represented by an isolated point."""

    HIGH = "high"
    LOW = "low"


class IsolatedPointStatus(Enum):
    """Whether an isolated point awaits or has passed right-side confirmation."""

    POTENTIAL = "potential"
    CONFIRMED = "confirmed"


@dataclass(frozen=True)
class IsolatedPoint:
    """A potential or confirmed isolated extreme in a candle sequence."""

    index: int
    kind: IsolatedPointKind
    status: IsolatedPointStatus
    price: float


def get_potential_isolated_point(
    left: Candle,
    current: Candle,
    index: int,
) -> IsolatedPoint | None:
    """Detect a potential isolated point before a right candle exists."""

    if current.high > left.high and current.low > left.low:
        return IsolatedPoint(
            index=index,
            kind=IsolatedPointKind.HIGH,
            status=IsolatedPointStatus.POTENTIAL,
            price=current.high,
        )
    if current.low < left.low and current.high < left.high:
        return IsolatedPoint(
            index=index,
            kind=IsolatedPointKind.LOW,
            status=IsolatedPointStatus.POTENTIAL,
            price=current.low,
        )
    return None


def confirm_isolated_point(
    point: IsolatedPoint,
    middle: Candle,
    right: Candle,
) -> IsolatedPoint | None:
    """Confirm a potential point using the full middle and right candles."""

    if point.kind is IsolatedPointKind.HIGH:
        confirmed = middle.high > right.high and middle.low > right.low
        price = middle.high
    else:
        confirmed = middle.low < right.low and middle.high < right.high
        price = middle.low

    if not confirmed:
        return None

    return IsolatedPoint(
        index=point.index,
        kind=point.kind,
        status=IsolatedPointStatus.CONFIRMED,
        price=price,
    )


def detect_confirmed_isolated_point(
    left: Candle,
    middle: Candle,
    right: Candle,
    index: int,
) -> IsolatedPoint | None:
    """Detect one strict confirmed isolated point from three candles."""

    potential = get_potential_isolated_point(left, middle, index)
    if potential is None:
        return None
    return confirm_isolated_point(potential, middle, right)


def find_confirmed_isolated_points(
    candles: Sequence[Candle],
) -> list[IsolatedPoint]:
    """Scan every immediate three-candle window in chronological order."""

    points: list[IsolatedPoint] = []
    for index in range(1, len(candles) - 1):
        point = detect_confirmed_isolated_point(
            candles[index - 1],
            candles[index],
            candles[index + 1],
            index,
        )
        if point is not None:
            points.append(point)
    return points


class IsolatedPointTracker:
    """Detect isolated-point state changes as closed candles arrive."""

    def __init__(self) -> None:
        self._previous_candle: Candle | None = None
        self._pending_point: IsolatedPoint | None = None
        self._next_index = 0

    def add_candle(self, candle: Candle) -> list[IsolatedPoint]:
        """Add one closed candle and return resulting point state changes."""

        index = self._next_index
        self._next_index += 1

        if self._previous_candle is None:
            self._previous_candle = candle
            return []

        changes: list[IsolatedPoint] = []
        if self._pending_point is not None:
            confirmed = confirm_isolated_point(
                self._pending_point,
                self._previous_candle,
                candle,
            )
            if confirmed is not None:
                changes.append(confirmed)

        self._pending_point = get_potential_isolated_point(
            self._previous_candle,
            candle,
            index,
        )
        if self._pending_point is not None:
            changes.append(self._pending_point)

        self._previous_candle = candle
        return changes
