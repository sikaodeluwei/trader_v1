"""Reproduce the frozen MNQ five-minute hierarchy oracle independently.

This utility intentionally uses only Python's standard library. It reads one
NinjaTrader OHLCV source file and writes fresh hierarchy artifacts to a caller-
selected directory. It never imports project modules or reads an existing
oracle or project-result file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


CASE_ID = "real-mnq-5m-validation"
LEVEL_SUFFIXES = {
    "isolated": "isolated_ground_truth.json",
    "short": "short_term_ground_truth.json",
    "medium": "medium_term_ground_truth.json",
    "long": "long_term_ground_truth.json",
}
Point = dict[str, Any]


def sha256(path: Path) -> str:
    """Return the lowercase SHA-256 digest of exact file bytes."""

    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_bytes(value: object) -> bytes:
    """Serialize exactly like the historical frozen oracle artifacts."""

    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def output_paths(source: Path, out_dir: Path) -> dict[str, Path]:
    suffix = "_250bars.txt"
    if not source.name.endswith(suffix):
        raise ValueError(f"source filename must end with {suffix!r}")
    stem = source.name[: -len(suffix)]
    return {
        level: out_dir / f"{stem}_{level_suffix}"
        for level, level_suffix in LEVEL_SUFFIXES.items()
    }


def parse_source(path: Path) -> list[Point]:
    """Parse and validate the source without sorting or resampling it."""

    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
    if len(lines) != 250:
        raise ValueError(f"source must contain exactly 250 rows, found {len(lines)}")

    rows: list[Point] = []
    for index, line in enumerate(lines):
        fields = line.split(";")
        if len(fields) != 6:
            raise ValueError(f"source row {index + 1} must contain six fields")
        stamp, open_text, high_text, low_text, close_text, volume_text = fields
        try:
            timestamp = datetime.strptime(stamp, "%Y%m%d %H%M%S")
            open_, high, low, close, volume = map(
                float,
                (open_text, high_text, low_text, close_text, volume_text),
            )
        except ValueError as error:
            raise ValueError(f"invalid source row {index + 1}") from error
        if not all(math.isfinite(value) for value in (open_, high, low, close, volume)):
            raise ValueError(f"source row {index + 1} contains a non-finite value")
        if high < max(open_, close) or low > min(open_, close) or high < low:
            raise ValueError(f"source row {index + 1} has invalid OHLC geometry")
        if volume < 0:
            raise ValueError(f"source row {index + 1} has negative volume")
        rows.append(
            {
                "index": index,
                "timestamp": timestamp,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
            }
        )

    for previous, current in zip(rows, rows[1:]):
        if current["timestamp"] - previous["timestamp"] != timedelta(minutes=5):
            raise ValueError("source timestamps must be consecutive five-minute intervals")
    return rows


def timestamp(row: Point) -> str:
    return row["timestamp"].strftime("%Y-%m-%d %H:%M:%S")


def source_metadata(source: Path) -> dict[str, object]:
    return {
        "filename": source.name,
        "instrument": "MNQ",
        "row_count": 250,
        "sha256": sha256(source),
        "start_index": 0,
        "timeframe": "5 minute",
    }


def potential_kind(left: Point, middle: Point) -> str | None:
    if middle["high"] > left["high"] and middle["low"] > left["low"]:
        return "HIGH"
    if middle["low"] < left["low"] and middle["high"] < left["high"]:
        return "LOW"
    return None


def is_strict_confirmation(kind: str, middle: Point, right: Point) -> bool:
    if kind == "HIGH":
        return middle["high"] > right["high"] and middle["low"] > right["low"]
    return middle["low"] < right["low"] and middle["high"] < right["high"]


def is_right_inside(middle: Point, right: Point) -> bool:
    return right["high"] <= middle["high"] and right["low"] >= middle["low"]


def structural_price(kind: str, row: Point) -> float:
    return row["high"] if kind == "HIGH" else row["low"]


def build_isolated(rows: list[Point], source: Path) -> dict[str, object]:
    confirmed = []
    for left, middle, right in zip(rows, rows[1:], rows[2:]):
        kind = potential_kind(left, middle)
        if kind is None:
            continue
        if is_strict_confirmation(kind, middle, right):
            basis = "STRICT"
        elif is_right_inside(middle, right):
            basis = "RIGHT_INSIDE_BAR"
        else:
            continue
        confirmed.append(
            {
                "confirmation_basis": basis,
                "confirmed_by": {
                    "index": right["index"],
                    "timestamp": timestamp(right),
                },
                "index": middle["index"],
                "kind": kind,
                "price": structural_price(kind, middle),
                "timestamp": timestamp(middle),
            }
        )

    unresolved = None
    kind = potential_kind(rows[-2], rows[-1])
    if kind is not None:
        unresolved = {
            "compared_with_left_index": rows[-2]["index"],
            "index": rows[-1]["index"],
            "kind": kind,
            "price": structural_price(kind, rows[-1]),
            "timestamp": timestamp(rows[-1]),
        }
    return {
        "case_id": CASE_ID,
        "confirmed": confirmed,
        "level": "ISOLATED",
        "schema_version": 1,
        "source": source_metadata(source),
        "unresolved_right_edge_potential": unresolved,
    }


def point_reference(point: Point, source_level: str | None = None) -> Point:
    result = {
        "index": point["index"],
        "kind": point["kind"],
        "price": point["price"],
        "timestamp": point["timestamp"],
    }
    if source_level is not None:
        result["source_level"] = source_level
    return result


def is_more_extreme(candidate: Point, current: Point) -> bool:
    if current["kind"] == "HIGH":
        return candidate["price"] > current["price"]
    return candidate["price"] < current["price"]


def normalize_same_kind(points: list[Point]) -> tuple[list[Point], list[Point]]:
    """Keep the most extreme point per run; equality keeps the earliest."""

    vertices: list[Point] = []
    suppressed: list[Point] = []
    run: list[Point] = []

    def flush() -> None:
        if not run:
            return
        winner = run[0]
        for candidate in run[1:]:
            if is_more_extreme(candidate, winner):
                winner = candidate
        vertices.append(winner)
        for item in run:
            if item is not winner:
                suppressed.append(
                    {
                        "point": deepcopy(item),
                        "reason": "CONSECUTIVE_SAME_KIND",
                        "retained_vertex": point_reference(winner),
                    }
                )

    for point in points:
        if run and point["kind"] != run[-1]["kind"]:
            flush()
            run = []
        run.append(point)
    flush()
    return vertices, suppressed


def pair_bounds(first: Point, second: Point) -> tuple[float, float] | None:
    if first["kind"] == second["kind"]:
        return None
    high = first if first["kind"] == "HIGH" else second
    low = first if first["kind"] == "LOW" else second
    return high["price"], low["price"]


def normalize_fixed_left_inside(points: list[Point]) -> tuple[list[Point], list[Point]]:
    """Apply only fixed-left non-overlapping pair containment until stable."""

    normalized = list(points)
    suppressed: list[Point] = []
    event = 0
    changed = True
    while changed:
        changed = False
        pair_start = 0
        while pair_start + 3 < len(normalized):
            earlier = normalized[pair_start : pair_start + 2]
            later = normalized[pair_start + 2 : pair_start + 4]
            earlier_bounds = pair_bounds(*earlier)
            later_bounds = pair_bounds(*later)
            contained = (
                earlier_bounds is not None
                and later_bounds is not None
                and later_bounds[0] <= earlier_bounds[0]
                and later_bounds[1] >= earlier_bounds[1]
            )
            if not contained:
                pair_start += 2
                continue
            event += 1
            for point in later:
                suppressed.append(
                    {
                        "containing_pair": [point_reference(item) for item in earlier],
                        "point": deepcopy(point),
                        "reason": "INSIDE_STRUCTURE",
                        "suppression_event": event,
                    }
                )
            del normalized[pair_start + 2 : pair_start + 4]
            changed = True
    return normalized, suppressed


def normalize(points: list[Point]) -> tuple[list[Point], list[Point]]:
    candidates, same_kind = normalize_same_kind(points)
    vertices, inside = normalize_fixed_left_inside(candidates)
    return vertices, same_kind + inside


def build_short(isolated: dict[str, object], source: Path) -> dict[str, object]:
    points = deepcopy(isolated["confirmed"])
    vertices, suppressed = normalize(points)
    return {
        "case_id": CASE_ID,
        "level": "SHORT",
        "points": points,
        "potentials": [],
        "schema_version": 1,
        "source": source_metadata(source),
        "suppressed": suppressed,
        "vertices": vertices,
    }


def source_reference(point: Point, source_level: str) -> Point:
    if source_level == "SHORT":
        return point_reference(point, source_level)
    result = deepcopy(point)
    result["source_level"] = source_level
    return result


def is_strict_pivot(previous: Point, pivot: Point, later: Point) -> bool:
    if pivot["kind"] == "HIGH":
        return previous["price"] < pivot["price"] > later["price"]
    return previous["price"] > pivot["price"] < later["price"]


def build_higher(
    lower: dict[str, object],
    *,
    level: str,
    source_level: str,
    source: Path,
) -> dict[str, object]:
    source_vertices = lower["vertices"]
    points: list[Point] = []
    potentials: list[Point] = []
    for kind in ("HIGH", "LOW"):
        same_kind = [point for point in source_vertices if point["kind"] == kind]
        for previous, pivot, later in zip(
            same_kind,
            same_kind[1:],
            same_kind[2:],
        ):
            if is_strict_pivot(previous, pivot, later):
                points.append(
                    {
                        "confirmed_by": source_reference(later, source_level),
                        "index": pivot["index"],
                        "kind": kind,
                        "previous_same_kind": source_reference(previous, source_level),
                        "price": pivot["price"],
                        "source_level": source_level,
                        "source_vertex": source_reference(pivot, source_level),
                        "timestamp": pivot["timestamp"],
                    }
                )
        if len(same_kind) >= 2 and is_more_extreme(same_kind[-1], same_kind[-2]):
            pivot = same_kind[-1]
            potentials.append(
                {
                    "index": pivot["index"],
                    "kind": kind,
                    "previous_same_kind": source_reference(same_kind[-2], source_level),
                    "price": pivot["price"],
                    "source_level": source_level,
                    "source_vertex": source_reference(pivot, source_level),
                    "timestamp": pivot["timestamp"],
                }
            )

    order = {point["index"]: position for position, point in enumerate(source_vertices)}
    points.sort(key=lambda point: order[point["index"]])
    potentials.sort(key=lambda point: order[point["index"]])
    vertices, suppressed = normalize(points)
    return {
        "case_id": CASE_ID,
        "level": level,
        "points": points,
        "potentials": potentials,
        "schema_version": 1,
        "source": source_metadata(source),
        "suppressed": suppressed,
        "vertices": vertices,
    }


def reproduce(source: Path, out_dir: Path) -> dict[str, Path]:
    rows = parse_source(source)
    isolated = build_isolated(rows, source)
    short = build_short(isolated, source)
    medium = build_higher(
        short,
        level="MEDIUM",
        source_level="SHORT",
        source=source,
    )
    long = build_higher(
        medium,
        level="LONG",
        source_level="MEDIUM",
        source=source,
    )
    paths = output_paths(source, out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for level, payload in (
        ("isolated", isolated),
        ("short", short),
        ("medium", medium),
        ("long", long),
    ):
        path = paths[level]
        if path.exists():
            raise FileExistsError(f"refusing to overwrite {path}")
        path.write_bytes(stable_bytes(payload))
    return paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = reproduce(args.source.resolve(), args.out_dir.resolve())
    result = {
        level: {"filename": path.name, "sha256": sha256(path)}
        for level, path in paths.items()
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
