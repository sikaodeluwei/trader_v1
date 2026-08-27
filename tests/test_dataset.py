import json
from pathlib import Path

import pytest

from trading.definitions.analysis import analyze_prices
from trading.definitions.candles import Advantage, CandleType
from trading.definitions.dataset import (
    CandleLabelRecord,
    create_record,
    load_records,
    record_to_sample,
    save_records,
)
from trading.definitions.features import get_features


def test_create_record_preserves_buyer_label() -> None:
    record = create_record([100, 101], Advantage.BUYER)

    assert record.prices == (100.0, 101.0)
    assert record.advantage is Advantage.BUYER


def test_create_record_preserves_seller_label() -> None:
    record = create_record([101, 100], Advantage.SELLER)

    assert record.prices == (101.0, 100.0)
    assert record.advantage is Advantage.SELLER


def test_create_record_preserves_none_label() -> None:
    record = create_record([100, 101, 100], Advantage.NONE)

    assert record.advantage is Advantage.NONE


def test_create_record_preserves_optional_candle_type_and_note() -> None:
    record = create_record(
        [91, 90, 110, 92],
        Advantage.SELLER,
        candle_type=CandleType.BULL_4,
        note="reviewed course example",
    )

    assert record.candle_type is CandleType.BULL_4
    assert record.note == "reviewed course example"


@pytest.mark.parametrize("prices", [[], [100]])
def test_create_record_rejects_fewer_than_two_prices(
    prices: list[float],
) -> None:
    with pytest.raises(ValueError, match="at least two"):
        create_record(prices, Advantage.NONE)


def test_record_to_sample_regenerates_features_from_ordered_prices() -> None:
    record = create_record(
        [91, 90, 110, 92],
        Advantage.SELLER,
        candle_type=CandleType.BULL_4,
    )

    sample = record_to_sample(record)

    assert sample.features == get_features(analyze_prices(record.prices))
    assert sample.advantage is Advantage.SELLER
    assert sample.candle_type is CandleType.BULL_4


def test_jsonl_round_trip_preserves_record_without_derived_features(
    tmp_path: Path,
) -> None:
    record = create_record(
        [91, 90, 110, 92],
        Advantage.SELLER,
        candle_type=CandleType.BULL_4,
        note="course-style bullish candle with seller advantage",
    )
    path = tmp_path / "candles.jsonl"

    save_records(path, [record])

    payload = json.loads(path.read_text(encoding="utf-8").strip())
    assert payload == {
        "prices": [91.0, 90.0, 110.0, 92.0],
        "advantage": "seller",
        "candle_type": "bull_4",
        "note": "course-style bullish candle with seller advantage",
    }
    assert load_records(path) == [record]


def test_multiple_records_save_and_load_in_order(tmp_path: Path) -> None:
    records = [
        create_record([100, 105, 110], Advantage.BUYER),
        create_record(
            [109, 110, 90, 108],
            Advantage.SELLER,
            candle_type=CandleType.BEAR_5,
        ),
        create_record([100, 90, 110, 100], Advantage.NONE, note="balanced"),
    ]
    path = tmp_path / "multiple.jsonl"

    save_records(path, records)

    assert load_records(path) == records
    assert len(path.read_text(encoding="utf-8").splitlines()) == 3


def test_candle_label_record_is_immutable() -> None:
    record = create_record([100, 101], Advantage.BUYER)

    with pytest.raises(AttributeError):
        record.note = "changed"  # type: ignore[misc]

    assert isinstance(record, CandleLabelRecord)
