"""Lesson 1 formation rules over explicit external annotations, never OHLC.

Boundaries, type labels, distinct relevant reactions and attempt outcomes
are supplied by the caller. A result checks these annotations conditionally;
it does not independently establish their truth or a currently active range.
"""

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from .key_levels import KeyLevelKind
from .market_structure import MarketSegment


class TradingRangeType(Enum):
    ORDINARY = "ordinary"
    SLOPING = "sloping"
    NARROW = "narrow"


class BoundaryOutcome(Enum):
    """Externally established event meanings; TOUCH establishes no reaction."""

    TOUCH = "touch"
    REACTION = "reaction"
    UNSUCCESSFUL_ATTEMPT = "unsuccessful_attempt"
    SUCCESSFUL_ATTEMPT = "successful_attempt"
    UNRESOLVED = "unresolved"


class RangeFormationStatus(Enum):
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    POTENTIAL = "potential"
    CONFIRMED = "confirmed"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class BoundaryAnchor:
    """A contact's candle index and price, not the time its boundary was selected."""

    index: int
    price: float

    def __post_init__(self) -> None:
        if not isfinite(self.price):
            raise ValueError("boundary anchor price must be finite")


@dataclass(frozen=True)
class RangeBoundary:
    """Explicit boundary anchors; no fitting, extrapolation or interpolation."""

    kind: KeyLevelKind
    anchors: tuple[BoundaryAnchor, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "anchors", tuple(self.anchors))
        if not isinstance(self.kind, KeyLevelKind):
            raise ValueError("boundary kind must be a KeyLevelKind")
        if not self.anchors:
            raise ValueError("boundary requires explicit anchors")
        if any(a.index >= b.index for a, b in zip(self.anchors, self.anchors[1:])):
            raise ValueError("boundary anchors must be strictly chronological")


@dataclass(frozen=True)
class BoundaryObservation:
    """One distinct event, with its outcome known at this observation index.

    The caller attests relevance to this context's boundary and independence
    from other events. An unresolved event supplies no failed-attempt proof.
    Index is an evidence-availability index, not a backdated initial touch.
    """

    index: int
    boundary: KeyLevelKind
    outcome: BoundaryOutcome

    def __post_init__(self) -> None:
        if not isinstance(self.boundary, KeyLevelKind):
            raise ValueError("observation boundary must be a KeyLevelKind")
        if not isinstance(self.outcome, BoundaryOutcome):
            raise ValueError("observation outcome must be a BoundaryOutcome")


@dataclass(frozen=True)
class TradingRangeContext:
    """A caller-selected segment and its externally annotated range evidence.

    An anchor is geometry, not a reaction. Re-anchoring or resolving an event
    requires a new explicit context; this is not a live stateful detector.
    known_at_index, when supplied, is when this complete annotation (including
    boundary selection) was known. None leaves historical availability unknown.
    """

    segment: MarketSegment
    range_type: TradingRangeType
    upper: RangeBoundary
    lower: RangeBoundary
    observations: tuple[BoundaryObservation, ...] = ()
    known_at_index: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "observations", tuple(self.observations))
        if not isinstance(self.range_type, TradingRangeType):
            raise ValueError("range_type must be a TradingRangeType")
        if (self.upper.kind is not KeyLevelKind.RESISTANCE
                or self.lower.kind is not KeyLevelKind.SUPPORT):
            raise ValueError("upper must be resistance and lower must be support")
        for boundary in (self.upper, self.lower):
            for anchor in boundary.anchors:
                if not self.segment.start_index <= anchor.index <= self.segment.end_index:
                    raise ValueError("boundary anchor is outside segment")
        upper_prices = {anchor.index: anchor.price for anchor in self.upper.anchors}
        for anchor in self.lower.anchors:
            if anchor.index in upper_prices and upper_prices[anchor.index] <= anchor.price:
                raise ValueError("upper boundary must exceed lower at shared anchors")
        if self.range_type is TradingRangeType.ORDINARY:
            for boundary in (self.upper, self.lower):
                if any(a.price != boundary.anchors[0].price for a in boundary.anchors):
                    raise ValueError("ordinary boundaries must be horizontal")
            if self.upper.anchors[0].price <= self.lower.anchors[0].price:
                raise ValueError("ordinary upper boundary must exceed lower boundary")
        previous_index = None
        for observation in self.observations:
            if not self.segment.start_index <= observation.index <= self.segment.end_index:
                raise ValueError("observation is outside segment")
            if previous_index is not None and observation.index <= previous_index:
                raise ValueError("distinct events require strictly chronological indexes")
            previous_index = observation.index
        if self.known_at_index is not None:
            if not isinstance(self.known_at_index, int) or isinstance(self.known_at_index, bool):
                raise ValueError("known_at_index must be an integer index")
            input_indexes = [
                anchor.index
                for boundary in (self.upper, self.lower)
                for anchor in boundary.anchors
            ] + [observation.index for observation in self.observations]
            if self.known_at_index < max(input_indexes):
                raise ValueError("known_at_index cannot precede anchors or outcome evidence")


@dataclass(frozen=True)
class RangeFormationResult:
    """Conditional formation evidence, dated only by context.known_at_index."""

    context: TradingRangeContext
    status: RangeFormationStatus
    reaction_count: int
    unsuccessful_upward_attempts: int
    unsuccessful_downward_attempts: int


def evaluate_range_formation(context: TradingRangeContext) -> RangeFormationResult:
    """Check course counts given already established, distinct relevant events.

    Failed upward attempts are externally labeled resistance events; failed
    downward attempts are support events. A mere reaction is not a failure.
    Successful attempts defer the lifecycle judgment to later lessons.
    CONFIRMED is limited to ordinary-range formation, conditional on inputs.
    """

    relevant_reactions = tuple(
        item for item in context.observations
        if item.outcome in {BoundaryOutcome.REACTION, BoundaryOutcome.UNSUCCESSFUL_ATTEMPT}
    )
    reactions = len(relevant_reactions)
    reaction_boundaries = {item.boundary for item in relevant_reactions}
    upward = sum(
        item.boundary is KeyLevelKind.RESISTANCE
        and item.outcome is BoundaryOutcome.UNSUCCESSFUL_ATTEMPT
        for item in context.observations
    )
    downward = sum(
        item.boundary is KeyLevelKind.SUPPORT
        and item.outcome is BoundaryOutcome.UNSUCCESSFUL_ATTEMPT
        for item in context.observations
    )
    if any(item.outcome is BoundaryOutcome.SUCCESSFUL_ATTEMPT for item in context.observations):
        status = RangeFormationStatus.UNRESOLVED
    elif context.range_type is TradingRangeType.ORDINARY and upward >= 2 and downward >= 2:
        status = RangeFormationStatus.CONFIRMED
    elif reactions >= 3 and reaction_boundaries == {
        KeyLevelKind.RESISTANCE, KeyLevelKind.SUPPORT,
    }:
        status = RangeFormationStatus.POTENTIAL
    else:
        status = RangeFormationStatus.INSUFFICIENT_EVIDENCE
    return RangeFormationResult(context, status, reactions, upward, downward)
