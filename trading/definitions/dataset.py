"""Storage for explicitly labeled ordered candle price paths.

Records persist source paths and human/course labels only. Derived analysis
and features are regenerated on demand so stored datasets cannot retain stale
feature calculations.
"""

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from .analysis import analyze_prices
from .candles import Advantage, CandleType
from .features import LabeledCandleSample, create_labeled_sample


@dataclass(frozen=True)
class CandleLabelRecord:
    """An immutable ordered price path with explicit calibration labels."""

    prices: tuple[float, ...]
    advantage: Advantage
    candle_type: CandleType | None = None
    note: str | None = None


def create_record(
    prices: Sequence[float],
    advantage: Advantage,
    candle_type: CandleType | None = None,
    note: str | None = None,
) -> CandleLabelRecord:
    """Create a record while preserving price order and supplied labels."""

    ordered_prices = tuple(float(price) for price in prices)
    if len(ordered_prices) < 2:
        raise ValueError("create_record requires at least two ordered prices")

    return CandleLabelRecord(
        prices=ordered_prices,
        advantage=advantage,
        candle_type=candle_type,
        note=note,
    )


def record_to_sample(record: CandleLabelRecord) -> LabeledCandleSample:
    """Regenerate analysis and features from a record's ordered price path."""

    analysis = analyze_prices(record.prices)
    return create_labeled_sample(
        analysis,
        record.advantage,
        candle_type=record.candle_type,
    )


def save_records(
    path: str | Path,
    records: Iterable[CandleLabelRecord],
) -> None:
    """Write records as JSON Lines without derived feature values."""

    with Path(path).open("w", encoding="utf-8", newline="\n") as output:
        for record in records:
            payload = {
                "prices": list(record.prices),
                "advantage": record.advantage.value,
                "candle_type": (
                    record.candle_type.value
                    if record.candle_type is not None
                    else None
                ),
                "note": record.note,
            }
            output.write(json.dumps(payload, ensure_ascii=False))
            output.write("\n")


def load_records(path: str | Path) -> list[CandleLabelRecord]:
    """Load JSONL records and restore their enum values."""

    records: list[CandleLabelRecord] = []
    with Path(path).open("r", encoding="utf-8") as source:
        for line in source:
            if not line.strip():
                continue

            payload = json.loads(line)
            candle_type_value = payload.get("candle_type")
            records.append(
                create_record(
                    prices=payload["prices"],
                    advantage=Advantage(payload["advantage"]),
                    candle_type=(
                        CandleType(candle_type_value)
                        if candle_type_value is not None
                        else None
                    ),
                    note=payload.get("note"),
                )
            )

    return records
