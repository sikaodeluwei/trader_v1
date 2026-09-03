"""Immutable validation models for offline market-structure analysis."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import isfinite
from typing import Generic, TypeVar

from trading.definitions.long_term_structure import LongTermPoint
from trading.definitions.market_structure import (
    MarketSegment,
    MarketState,
    StructurePoint,
)
from trading.definitions.medium_term_structure import MediumTermPoint
from trading.definitions.pullback_structure import BMSResult
from trading.definitions.short_term_structure import ShortTermPoint
from trading.definitions.sms_structure import SMSResult

T = TypeVar("T")


class EvaluationStatus(Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"


class EvaluationReason(Enum):
    INSUFFICIENT_STRUCTURE = "insufficient_structure"
    INTRABAR_DATA_UNAVAILABLE = "intrabar_data_unavailable"
    CANDLE_TYPE_UNCALIBRATED = "candle_type_uncalibrated"
    BOUNDARY_NOT_CANONICAL_VERTEX = "boundary_not_canonical_vertex"
    INVALID_CONTEXT = "invalid_context"
    PARENT_STATE_NOT_DIRECTIONAL = "parent_state_not_directional"
    OHLC_INTRABAR_ORDER_AMBIGUOUS = "ohlc_intrabar_order_ambiguous"


@dataclass(frozen=True)
class Evaluation(Generic[T]):
    status: EvaluationStatus
    value: T | None = None
    reason: EvaluationReason | None = None
    message: str | None = None

    def __post_init__(self) -> None:
        if self.status is EvaluationStatus.AVAILABLE:
            if self.value is None or self.reason is not None:
                raise ValueError("AVAILABLE evaluation requires a value and no reason")
        elif self.status in {EvaluationStatus.UNAVAILABLE, EvaluationStatus.INVALID}:
            if self.value is not None or self.reason is None:
                raise ValueError("UNAVAILABLE or INVALID evaluation requires a reason and no value")


@dataclass(frozen=True)
class ClosedCandleObservation:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    intrabar_prices: tuple[float, ...] | None = None

    def __post_init__(self) -> None:
        if self.intrabar_prices is not None:
            object.__setattr__(self, "intrabar_prices", tuple(self.intrabar_prices))
        if self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        ohlc = (self.open, self.high, self.low, self.close)
        if not all(isfinite(value) for value in ohlc):
            raise ValueError("OHLC values must be finite")
        if not self.low <= min(self.open, self.close) <= max(self.open, self.close) <= self.high:
            raise ValueError("low <= min(open, close) <= max(open, close) <= high")
        if self.intrabar_prices is not None:
            if not all(isfinite(price) for price in self.intrabar_prices):
                raise ValueError("intrabar prices must be finite")
            if len(self.intrabar_prices) >= 2:
                derived = (
                    self.intrabar_prices[0],
                    max(self.intrabar_prices),
                    min(self.intrabar_prices),
                    self.intrabar_prices[-1],
                )
                supplied = (self.open, self.high, self.low, self.close)
                if derived != supplied:
                    raise ValueError("intrabar prices must derive the supplied OHLC exactly")


@dataclass(frozen=True)
class OfflineMarketWindow:
    instrument: str
    timeframe: str
    start_index: int
    candles: tuple[ClosedCandleObservation, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "candles", tuple(self.candles))
        if not self.instrument:
            raise ValueError("instrument must be non-empty")
        if not self.timeframe:
            raise ValueError("timeframe must be non-empty")
        if not 1 <= len(self.candles) <= 250:
            raise ValueError("candles must contain 1 through 250 observations")
        for previous, current in zip(self.candles, self.candles[1:]):
            if not previous.timestamp < current.timestamp:
                raise ValueError("candle timestamps must be strictly increasing")


class StructuralLevel(Enum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


@dataclass(frozen=True)
class BMSAnalysisRequest:
    trend_origin_index: int
    previous_extreme_index: int
    pullback_extreme_index: int


@dataclass(frozen=True)
class SMSAnalysisRequest:
    trend_extreme_index: int
    creator_point_index: int


@dataclass(frozen=True)
class SegmentAnalysisRequest:
    segment: MarketSegment
    level: StructuralLevel
    bms: BMSAnalysisRequest | None = None
    sms: SMSAnalysisRequest | None = None


StructuralVertex = ShortTermPoint | MediumTermPoint | LongTermPoint


@dataclass(frozen=True)
class ResolvedStructurePoint:
    level: StructuralLevel
    source_vertex: StructuralVertex
    point: StructurePoint


@dataclass(frozen=True)
class SegmentAnalysisResult:
    request: SegmentAnalysisRequest
    selected_points: tuple[ResolvedStructurePoint, ...]
    market_state: Evaluation[MarketState]
    bms: Evaluation[BMSResult] | None
    sms: Evaluation[SMSResult] | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "selected_points", tuple(self.selected_points))
