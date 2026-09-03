"""Offline batch scanning for deformation-aware isolated point recognitions."""

from collections.abc import Sequence
from dataclasses import dataclass

from trading.definitions.candles import Candle
from trading.definitions.isolated_point_deformations import (
    DeformationAwareIsolatedPointTracker,
    IsolatedPointBasis,
    IsolatedPointRecognition,
)
from trading.definitions.isolated_points import IsolatedPoint


@dataclass(frozen=True)
class IsolatedPointScan:
    recognitions: tuple[IsolatedPointRecognition, ...]
    unresolved_potential: IsolatedPoint | None


def find_isolated_point_recognitions(
    candles: Sequence[Candle], *, start_index: int = 0
) -> IsolatedPointScan:
    tracker = DeformationAwareIsolatedPointTracker()
    recognitions: list[IsolatedPointRecognition] = []
    unresolved_potential: IsolatedPoint | None = None

    for candle in candles:
        changes = tracker.add_candle(candle)
        if unresolved_potential is not None:
            unresolved_potential = None
        for change in changes:
            if isinstance(change, IsolatedPointRecognition):
                point = change.point
                recognitions.append(
                    IsolatedPointRecognition(
                        point=IsolatedPoint(
                            index=point.index + start_index,
                            kind=point.kind,
                            status=point.status,
                            price=point.price,
                        ),
                        basis=change.basis,
                    )
                )
            else:
                unresolved_potential = IsolatedPoint(
                    index=change.index + start_index,
                    kind=change.kind,
                    status=change.status,
                    price=change.price,
                )

    return IsolatedPointScan(tuple(recognitions), unresolved_potential)
