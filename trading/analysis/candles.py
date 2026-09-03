"""Offline composition for one validated, closed candle observation."""

from dataclasses import dataclass
from datetime import datetime

from trading.definitions.analysis import CandleAnalysis, analyze_prices
from trading.definitions.candles import (
    Candle,
    CandleControl,
    CandleGeometry,
    CandleSide,
    CandleType,
    get_control,
    get_geometry,
    get_side,
)
from trading.definitions.features import CandleFeatures, get_features

from .models import (
    ClosedCandleObservation,
    Evaluation,
    EvaluationReason,
    EvaluationStatus,
)


@dataclass(frozen=True)
class OfflineCandleResult:
    """Measurements and explicitly unavailable capabilities for one candle."""

    index: int
    timestamp: datetime
    observation: ClosedCandleObservation
    candle: Candle
    side: CandleSide
    geometry: CandleGeometry
    control: CandleControl
    intrabar_analysis: Evaluation[CandleAnalysis]
    features: Evaluation[CandleFeatures]
    candle_type: Evaluation[CandleType]


def analyze_closed_candle(
    observation: ClosedCandleObservation,
    *,
    index: int,
) -> OfflineCandleResult:
    """Compose existing candle measurements for one closed observation."""

    candle = Candle(observation.open, observation.high, observation.low, observation.close)
    side = get_side(candle)
    geometry = get_geometry(candle)
    control = get_control(candle)

    if observation.intrabar_prices is None or len(observation.intrabar_prices) < 2:
        intrabar = Evaluation(
            EvaluationStatus.UNAVAILABLE,
            reason=EvaluationReason.INTRABAR_DATA_UNAVAILABLE,
        )
        features = Evaluation(
            EvaluationStatus.UNAVAILABLE,
            reason=EvaluationReason.INTRABAR_DATA_UNAVAILABLE,
        )
    else:
        analysis = analyze_prices(observation.intrabar_prices)
        intrabar = Evaluation(EvaluationStatus.AVAILABLE, value=analysis)
        features = Evaluation(EvaluationStatus.AVAILABLE, value=get_features(analysis))

    candle_type = Evaluation(
        EvaluationStatus.UNAVAILABLE,
        reason=EvaluationReason.CANDLE_TYPE_UNCALIBRATED,
    )
    return OfflineCandleResult(
        index=index,
        timestamp=observation.timestamp,
        observation=observation,
        candle=candle,
        side=side,
        geometry=geometry,
        control=control,
        intrabar_analysis=intrabar,
        features=features,
        candle_type=candle_type,
    )
