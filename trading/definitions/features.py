"""Flat candle features and explicit human-label samples.

Features collect existing measurements for later calibration, fuzzy logic, or
learned classification. This module does not assign advantage or candle type.
"""

from dataclasses import dataclass

from .analysis import CandleAnalysis
from .candles import Advantage, CandleSide, CandleType
from .extremes import ExtremeOrder
from .movements import MovementSide


@dataclass(frozen=True)
class CandleFeatures:
    """A flat, immutable collection of candle-analysis measurements."""

    side: CandleSide
    body_ratio: float
    upper_wick_ratio: float
    lower_wick_ratio: float
    open_position: float
    close_position: float
    control_score: float
    extreme_order: ExtremeOrder
    initial_side: MovementSide | None
    initial_ratio: float
    final_side: MovementSide | None
    final_ratio: float
    displacement_ratio: float
    total_buyer_movement_ratio: float
    total_seller_movement_ratio: float


@dataclass(frozen=True)
class LabeledCandleSample:
    """Candle features paired with an explicitly supplied calibration label."""

    features: CandleFeatures
    advantage: Advantage
    candle_type: CandleType | None = None


def get_features(analysis: CandleAnalysis) -> CandleFeatures:
    """Flatten existing candle-analysis measurements without classifying them."""

    total_range = analysis.candle.high - analysis.candle.low
    if total_range == 0:
        total_buyer_movement_ratio = 0.0
        total_seller_movement_ratio = 0.0
    else:
        total_buyer_movement_ratio = (
            analysis.movements.total_buyer_movement / total_range
        )
        total_seller_movement_ratio = (
            analysis.movements.total_seller_movement / total_range
        )

    return CandleFeatures(
        side=analysis.side,
        body_ratio=analysis.geometry.body_ratio,
        upper_wick_ratio=analysis.geometry.upper_wick_ratio,
        lower_wick_ratio=analysis.geometry.lower_wick_ratio,
        open_position=analysis.geometry.open_position,
        close_position=analysis.geometry.close_position,
        control_score=analysis.control.control_score,
        extreme_order=analysis.extreme_evidence.order,
        initial_side=analysis.extreme_evidence.initial_side,
        initial_ratio=analysis.extreme_evidence.initial_ratio,
        final_side=analysis.extreme_evidence.final_side,
        final_ratio=analysis.extreme_evidence.final_ratio,
        displacement_ratio=analysis.extreme_evidence.displacement_ratio,
        total_buyer_movement_ratio=total_buyer_movement_ratio,
        total_seller_movement_ratio=total_seller_movement_ratio,
    )


def create_labeled_sample(
    analysis: CandleAnalysis,
    advantage: Advantage,
    candle_type: CandleType | None = None,
) -> LabeledCandleSample:
    """Pair features with caller-supplied course or human labels."""

    return LabeledCandleSample(
        features=get_features(analysis),
        advantage=advantage,
        candle_type=candle_type,
    )
