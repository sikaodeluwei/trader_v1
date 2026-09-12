"""Strictly compare frozen MNQ five-minute oracle and project artifacts.

The adapters in this module normalize only documented representation
differences. Ordered collections remain ordered, prices use ``Decimal``, and
oracle-only provenance is validated before cross-schema comparison.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable


Json = dict[str, Any]


class AdapterError(ValueError):
    """A stable-path schema or provenance error."""

    def __init__(self, path: str, message: str):
        super().__init__(message)
        self.path = path


def load_json(path: Path) -> Json:
    return json.loads(
        path.read_text(encoding="utf-8"),
        parse_float=Decimal,
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decimal(value: object, path: str) -> Decimal:
    if isinstance(value, bool):
        raise AdapterError(path, "boolean is not a numeric price")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    raise AdapterError(path, "numeric price is missing or has an invalid type")


def integer(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise AdapterError(path, "index must be an integer")
    return value


def text(value: object, path: str) -> str:
    if not isinstance(value, str):
        raise AdapterError(path, "text field is missing or has an invalid type")
    return value


def canonical_token(value: object, path: str) -> str:
    """Normalize only enum-name casing; no semantic aliases are accepted."""

    return text(value, path).upper()


def jsonable(value: object) -> object:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [jsonable(item) for item in value]
    return value


def stable_bytes(value: object) -> bytes:
    return (
        json.dumps(
            jsonable(value),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def mutation_bytes(value: object) -> bytes:
    """Serialize temporary controls with Decimal values kept as JSON numbers."""

    def convert(item: object) -> object:
        if isinstance(item, Decimal):
            return float(item)
        if isinstance(item, dict):
            return {key: convert(child) for key, child in item.items()}
        if isinstance(item, list):
            return [convert(child) for child in item]
        return item

    return (json.dumps(convert(value), indent=2, sort_keys=True) + "\n").encode("utf-8")


def parse_source(path: Path) -> list[Json]:
    rows = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        fields = line.split(";")
        if len(fields) != 6:
            raise AdapterError(f"/source/{index}", "source row must have six fields")
        stamp, open_, high, low, close, volume = fields
        datetime.strptime(stamp, "%Y%m%d %H%M%S")
        rows.append(
            {
                "index": index,
                "timestamp": datetime.strptime(stamp, "%Y%m%d %H%M%S").strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "open": Decimal(open_),
                "high": Decimal(high),
                "low": Decimal(low),
                "close": Decimal(close),
                "volume": Decimal(volume),
            }
        )
    return rows


def source_clock(value: object, path: str) -> str:
    """Retain source clock fields; allow only a zero-offset technical suffix."""

    raw = text(value, path)
    parsed = datetime.fromisoformat(raw)
    if parsed.utcoffset() is not None and parsed.utcoffset().total_seconds() != 0:
        raise AdapterError(path, "project timestamp changes the source clock offset")
    return parsed.replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")


def expected_isolated_point(item: Json, path: str) -> Json:
    """Project the rich oracle recognition without discarding its confirmer."""

    confirmer = item.get("confirmed_by")
    if not isinstance(confirmer, dict):
        raise AdapterError(f"{path}/confirmed_by", "missing confirmer provenance")
    return {
        "index": integer(item.get("index"), f"{path}/index"),
        "kind": canonical_token(item.get("kind"), f"{path}/kind"),
        "price": decimal(item.get("price"), f"{path}/price"),
        "timestamp": text(item.get("timestamp"), f"{path}/timestamp"),
        "basis": canonical_token(
            item.get("confirmation_basis"), f"{path}/confirmation_basis"
        ),
        "status": "CONFIRMED",
        "confirmed_by": {
            "index": integer(confirmer.get("index"), f"{path}/confirmed_by/index"),
            "timestamp": text(
                confirmer.get("timestamp"), f"{path}/confirmed_by/timestamp"
            ),
        },
    }


def actual_isolated_point(item: Json, rows: list[Json], path: str) -> Json:
    """Expand the project recognition's implicit next-candle confirmer."""

    point = item.get("point")
    if not isinstance(point, dict):
        raise AdapterError(f"{path}/point", "missing isolated point")
    index = integer(point.get("index"), f"{path}/point/index")
    if index + 1 >= len(rows):
        raise AdapterError(f"{path}/point/index", "confirmed point lacks next candle")
    return {
        "index": index,
        "kind": canonical_token(point.get("kind"), f"{path}/point/kind"),
        "price": decimal(point.get("price"), f"{path}/point/price"),
        "timestamp": rows[index]["timestamp"],
        "basis": canonical_token(item.get("basis"), f"{path}/basis"),
        "status": canonical_token(point.get("status"), f"{path}/point/status"),
        "confirmed_by": {
            "index": index + 1,
            "timestamp": rows[index + 1]["timestamp"],
        },
    }


def expected_unresolved(item: object, path: str) -> object:
    if item is None:
        return None
    if not isinstance(item, dict):
        raise AdapterError(path, "invalid unresolved point")
    return {
        "index": integer(item.get("index"), f"{path}/index"),
        "kind": canonical_token(item.get("kind"), f"{path}/kind"),
        "price": decimal(item.get("price"), f"{path}/price"),
        "timestamp": text(item.get("timestamp"), f"{path}/timestamp"),
        "status": "POTENTIAL",
        "compared_with_left_index": integer(
            item.get("compared_with_left_index"),
            f"{path}/compared_with_left_index",
        ),
    }


def actual_unresolved(item: object, rows: list[Json], path: str) -> object:
    if item is None:
        return None
    if not isinstance(item, dict):
        raise AdapterError(path, "invalid unresolved point")
    index = integer(item.get("index"), f"{path}/index")
    return {
        "index": index,
        "kind": canonical_token(item.get("kind"), f"{path}/kind"),
        "price": decimal(item.get("price"), f"{path}/price"),
        "timestamp": rows[index]["timestamp"],
        "status": canonical_token(item.get("status"), f"{path}/status"),
        "compared_with_left_index": index - 1,
    }


def expected_short_point(item: Json, path: str) -> Json:
    """Keep all short recognition semantics stored by the oracle."""

    return expected_isolated_point(item, path)


def actual_short_point(
    item: Json,
    isolated_by_index: dict[int, Json],
    path: str,
) -> Json:
    """Join a project short point to its exact canonical isolated recognition."""

    index = integer(item.get("index"), f"{path}/index")
    if index not in isolated_by_index:
        raise AdapterError(f"{path}/index", "short point is not a confirmed isolated point")
    recognition = isolated_by_index[index]
    projected = deepcopy(recognition)
    raw_kind = canonical_token(item.get("kind"), f"{path}/kind")
    raw_price = decimal(item.get("price"), f"{path}/price")
    raw_basis = canonical_token(
        item.get("recognition_basis"), f"{path}/recognition_basis"
    )
    if (raw_kind, raw_price, raw_basis) != (
        projected["kind"],
        projected["price"],
        projected["basis"],
    ):
        raise AdapterError(path, "short point disagrees with isolated provenance")
    return projected


def point_ref(point: Json) -> Json:
    return {
        "index": point["index"],
        "kind": point["kind"],
        "price": point["price"],
        "timestamp": point["timestamp"],
    }


def validate_expected_short_point_ref(
    raw: object,
    short_by_index: dict[int, Json],
    path: str,
) -> Json:
    """Resolve one oracle SHORT reference without discarding its identity."""

    if not isinstance(raw, dict):
        raise AdapterError(path, "missing SHORT point reference")
    index = integer(raw.get("index"), f"{path}/index")
    if index not in short_by_index:
        raise AdapterError(f"{path}/index", "reference is not a canonical SHORT point")
    canonical = short_by_index[index]
    observed = {
        "index": index,
        "kind": canonical_token(raw.get("kind"), f"{path}/kind"),
        "price": decimal(raw.get("price"), f"{path}/price"),
        "timestamp": text(raw.get("timestamp"), f"{path}/timestamp"),
    }
    if observed != point_ref(canonical):
        raise AdapterError(path, "SHORT point reference is not exact")
    return canonical


def _short_is_more_extreme(candidate: Json, current: Json) -> bool:
    if current["kind"] == "HIGH":
        return candidate["price"] > current["price"]
    return candidate["price"] < current["price"]


def _short_pair_bounds(first: Json, second: Json) -> tuple[Decimal, Decimal] | None:
    if first["kind"] == second["kind"]:
        return None
    high = first if first["kind"] == "HIGH" else second
    low = first if first["kind"] == "LOW" else second
    return high["price"], low["price"]


def derive_short_suppression_provenance(points: list[Json]) -> list[Json]:
    """Reconstruct deterministic suppression evidence from canonical points.

    The production structure stores only the suppressed point and reason.  The
    oracle additionally records the retained same-kind vertex or fixed-left
    containing pair and event.  Replaying the approved normalization makes
    those oracle-only fields independently comparable instead of dropping
    them from the cross-schema audit.
    """

    vertices: list[Json] = []
    same_kind_suppressed: list[Json] = []
    run: list[Json] = []

    def flush() -> None:
        if not run:
            return
        winner = run[0]
        for candidate in run[1:]:
            if _short_is_more_extreme(candidate, winner):
                winner = candidate
        vertices.append(winner)
        for point in run:
            if point is not winner:
                same_kind_suppressed.append(
                    {
                        "point": point,
                        "reason": "CONSECUTIVE_SAME_KIND",
                        "retained_vertex": point_ref(winner),
                    }
                )

    for point in points:
        if run and point["kind"] != run[-1]["kind"]:
            flush()
            run = []
        run.append(point)
    flush()

    normalized = list(vertices)
    inside_suppressed: list[Json] = []
    event = 0
    changed = True
    while changed:
        changed = False
        pair_start = 0
        while pair_start + 3 < len(normalized):
            earlier = normalized[pair_start : pair_start + 2]
            later = normalized[pair_start + 2 : pair_start + 4]
            earlier_bounds = _short_pair_bounds(*earlier)
            later_bounds = _short_pair_bounds(*later)
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
                inside_suppressed.append(
                    {
                        "containing_pair": [point_ref(item) for item in earlier],
                        "point": point,
                        "reason": "INSIDE_STRUCTURE",
                        "suppression_event": event,
                    }
                )
            del normalized[pair_start + 2 : pair_start + 4]
            changed = True
    return same_kind_suppressed + inside_suppressed


def expected_short_suppression(
    item: Json,
    short_by_index: dict[int, Json],
    path: str,
) -> Json:
    """Canonicalize every rich oracle suppression-provenance field."""

    reason = canonical_token(item.get("reason"), f"{path}/reason")
    point_raw = item.get("point")
    if not isinstance(point_raw, dict):
        raise AdapterError(f"{path}/point", "missing suppressed SHORT point")
    point = expected_short_point(point_raw, f"{path}/point")
    if point["index"] not in short_by_index or point != short_by_index[point["index"]]:
        raise AdapterError(f"{path}/point", "suppressed point is not canonical SHORT evidence")

    if reason == "CONSECUTIVE_SAME_KIND":
        if set(item) != {"point", "reason", "retained_vertex"}:
            raise AdapterError(path, "same-kind suppression fields are incomplete or unexpected")
        retained = validate_expected_short_point_ref(
            item.get("retained_vertex"),
            short_by_index,
            f"{path}/retained_vertex",
        )
        return {
            "point": point,
            "reason": reason,
            "retained_vertex": point_ref(retained),
        }

    if reason == "INSIDE_STRUCTURE":
        if set(item) != {"containing_pair", "point", "reason", "suppression_event"}:
            raise AdapterError(path, "inside suppression fields are incomplete or unexpected")
        pair_raw = item.get("containing_pair")
        if not isinstance(pair_raw, list) or len(pair_raw) != 2:
            raise AdapterError(f"{path}/containing_pair", "containing pair must have two points")
        pair = [
            validate_expected_short_point_ref(
                raw,
                short_by_index,
                f"{path}/containing_pair/{index}",
            )
            for index, raw in enumerate(pair_raw)
        ]
        return {
            "containing_pair": [point_ref(value) for value in pair],
            "point": point,
            "reason": reason,
            "suppression_event": integer(
                item.get("suppression_event"), f"{path}/suppression_event"
            ),
        }

    raise AdapterError(f"{path}/reason", "unknown SHORT suppression reason")


def validate_expected_short_ref(
    raw: object,
    short_by_index: dict[int, Json],
    path: str,
) -> Json:
    if not isinstance(raw, dict):
        raise AdapterError(path, "missing SHORT provenance reference")
    index = integer(raw.get("index"), f"{path}/index")
    if index not in short_by_index:
        raise AdapterError(f"{path}/index", "reference is not a canonical SHORT point")
    canonical = short_by_index[index]
    expected_raw = point_ref(canonical) | {"source_level": "SHORT"}
    observed = {
        "index": index,
        "kind": canonical_token(raw.get("kind"), f"{path}/kind"),
        "price": decimal(raw.get("price"), f"{path}/price"),
        "timestamp": text(raw.get("timestamp"), f"{path}/timestamp"),
        "source_level": canonical_token(
            raw.get("source_level"), f"{path}/source_level"
        ),
    }
    if observed != expected_raw:
        raise AdapterError(path, "SHORT provenance reference is not exact")
    return canonical


def previous_same_kind(vertices: list[Json], pivot_index: int, path: str) -> Json:
    position = next(
        (position for position, point in enumerate(vertices) if point["index"] == pivot_index),
        None,
    )
    if position is None:
        raise AdapterError(path, "pivot is not a canonical source vertex")
    pivot = vertices[position]
    for candidate in reversed(vertices[:position]):
        if candidate["kind"] == pivot["kind"]:
            return candidate
    raise AdapterError(path, "pivot lacks previous same-kind source vertex")


def previous_same_kind_medium(
    vertices: list[Json], pivot_index: int, path: str
) -> Json:
    position = next(
        (
            position
            for position, point in enumerate(vertices)
            if point["pivot"]["index"] == pivot_index
        ),
        None,
    )
    if position is None:
        raise AdapterError(path, "pivot is not a canonical MEDIUM vertex")
    kind = vertices[position]["pivot"]["kind"]
    for candidate in reversed(vertices[:position]):
        if candidate["pivot"]["kind"] == kind:
            return candidate
    raise AdapterError(path, "pivot lacks previous same-kind MEDIUM vertex")


def expected_medium_point(
    item: Json,
    short_by_index: dict[int, Json],
    path: str,
    *,
    potential: bool = False,
) -> Json:
    """Resolve flattened oracle MEDIUM refs to complete canonical SHORT data."""

    pivot = validate_expected_short_ref(
        item.get("source_vertex"), short_by_index, f"{path}/source_vertex"
    )
    previous = validate_expected_short_ref(
        item.get("previous_same_kind"),
        short_by_index,
        f"{path}/previous_same_kind",
    )
    top = {
        "index": integer(item.get("index"), f"{path}/index"),
        "kind": canonical_token(item.get("kind"), f"{path}/kind"),
        "price": decimal(item.get("price"), f"{path}/price"),
        "timestamp": text(item.get("timestamp"), f"{path}/timestamp"),
    }
    if top != point_ref(pivot):
        raise AdapterError(path, "MEDIUM top-level identity differs from source vertex")
    result = {
        "pivot": pivot,
        "previous_same_kind": previous,
        "source_level": canonical_token(
            item.get("source_level"), f"{path}/source_level"
        ),
        "status": "POTENTIAL" if potential else "CONFIRMED",
    }
    if result["source_level"] != "SHORT":
        raise AdapterError(f"{path}/source_level", "MEDIUM source must be SHORT")
    if not potential:
        result["confirmed_by"] = validate_expected_short_ref(
            item.get("confirmed_by"), short_by_index, f"{path}/confirmed_by"
        )
    return result


def actual_medium_point(
    item: Json,
    short_by_index: dict[int, Json],
    short_vertices: list[Json],
    path: str,
    *,
    potential: bool = False,
) -> Json:
    """Expand nested project MEDIUM records without dropping SHORT basis data."""

    pivot_raw = item.get("pivot")
    if not isinstance(pivot_raw, dict):
        raise AdapterError(f"{path}/pivot", "missing nested SHORT pivot")
    pivot = actual_short_point(pivot_raw, short_by_index, f"{path}/pivot")
    result = {
        "pivot": pivot,
        "previous_same_kind": previous_same_kind(
            short_vertices, pivot["index"], f"{path}/pivot/index"
        ),
        "source_level": "SHORT",
        "status": "POTENTIAL" if potential else "CONFIRMED",
    }
    if potential:
        previous_raw = item.get("previous_same_kind")
        if not isinstance(previous_raw, dict):
            raise AdapterError(
                f"{path}/previous_same_kind", "missing potential provenance"
            )
        observed_previous = actual_short_point(
            previous_raw, short_by_index, f"{path}/previous_same_kind"
        )
        if observed_previous != result["previous_same_kind"]:
            raise AdapterError(
                f"{path}/previous_same_kind",
                "potential previous source is not immediate same-kind vertex",
            )
    else:
        confirmed_raw = item.get("confirmed_by")
        if not isinstance(confirmed_raw, dict):
            raise AdapterError(f"{path}/confirmed_by", "missing MEDIUM confirmer")
        result["confirmed_by"] = actual_short_point(
            confirmed_raw, short_by_index, f"{path}/confirmed_by"
        )
    return result


def medium_identity(point: Json) -> tuple[int, str, Decimal]:
    pivot = point["pivot"]
    return pivot["index"], pivot["kind"], pivot["price"]


def validate_expected_medium_ref(
    raw: object,
    medium_by_index: dict[int, Json],
    short_by_index: dict[int, Json],
    path: str,
) -> Json:
    if not isinstance(raw, dict):
        raise AdapterError(path, "missing MEDIUM provenance reference")
    index = integer(raw.get("index"), f"{path}/index")
    if index not in medium_by_index:
        raise AdapterError(f"{path}/index", "reference is not a canonical MEDIUM point")
    canonical = medium_by_index[index]
    if canonical_token(raw.get("source_level"), f"{path}/source_level") != "MEDIUM":
        raise AdapterError(f"{path}/source_level", "LONG source must be MEDIUM")
    nested_medium = deepcopy(raw)
    # The oracle relabels the copied MEDIUM record at the LONG boundary. Its
    # own nested source_vertex/confirmed_by records remain SHORT provenance.
    nested_medium["source_level"] = "SHORT"
    reconstructed = expected_medium_point(nested_medium, short_by_index, path)
    if canonical != reconstructed:
        raise AdapterError(path, "embedded MEDIUM provenance is not exact")
    return canonical


def expected_long_point(
    item: Json,
    medium_by_index: dict[int, Json],
    short_by_index: dict[int, Json],
    path: str,
    *,
    potential: bool = False,
) -> Json:
    """Resolve LONG through source_vertex, avoiding the historical wrong field."""

    pivot = validate_expected_medium_ref(
        item.get("source_vertex"),
        medium_by_index,
        short_by_index,
        f"{path}/source_vertex",
    )
    previous = validate_expected_medium_ref(
        item.get("previous_same_kind"),
        medium_by_index,
        short_by_index,
        f"{path}/previous_same_kind",
    )
    top = {
        "index": integer(item.get("index"), f"{path}/index"),
        "kind": canonical_token(item.get("kind"), f"{path}/kind"),
        "price": decimal(item.get("price"), f"{path}/price"),
        "timestamp": text(item.get("timestamp"), f"{path}/timestamp"),
    }
    if top != point_ref(pivot["pivot"]):
        raise AdapterError(path, "LONG top-level identity differs from source vertex")
    result = {
        "pivot": pivot,
        "previous_same_kind": previous,
        "source_level": canonical_token(
            item.get("source_level"), f"{path}/source_level"
        ),
        "status": "POTENTIAL" if potential else "CONFIRMED",
    }
    if result["source_level"] != "MEDIUM":
        raise AdapterError(f"{path}/source_level", "LONG source must be MEDIUM")
    if not potential:
        result["confirmed_by"] = validate_expected_medium_ref(
            item.get("confirmed_by"),
            medium_by_index,
            short_by_index,
            f"{path}/confirmed_by",
        )
    return result


def actual_long_point(
    item: Json,
    medium_by_index: dict[int, Json],
    medium_vertices: list[Json],
    short_by_index: dict[int, Json],
    short_vertices: list[Json],
    path: str,
    *,
    potential: bool = False,
) -> Json:
    """Expand nested project LONG data into complete MEDIUM provenance."""

    pivot_raw = item.get("pivot")
    if not isinstance(pivot_raw, dict):
        raise AdapterError(f"{path}/pivot", "missing nested MEDIUM pivot")
    pivot = actual_medium_point(
        pivot_raw,
        short_by_index,
        short_vertices,
        f"{path}/pivot",
    )
    pivot_index = pivot["pivot"]["index"]
    result = {
        "pivot": pivot,
        "previous_same_kind": previous_same_kind_medium(
            medium_vertices, pivot_index, f"{path}/pivot/pivot/index"
        ),
        "source_level": "MEDIUM",
        "status": "POTENTIAL" if potential else "CONFIRMED",
    }
    if potential:
        previous_raw = item.get("previous_same_kind")
        if not isinstance(previous_raw, dict):
            raise AdapterError(
                f"{path}/previous_same_kind", "missing LONG potential provenance"
            )
        observed_previous = actual_medium_point(
            previous_raw,
            short_by_index,
            short_vertices,
            f"{path}/previous_same_kind",
        )
        if observed_previous != result["previous_same_kind"]:
            raise AdapterError(
                f"{path}/previous_same_kind",
                "LONG potential previous source is not immediate same-kind vertex",
            )
    else:
        confirmed_raw = item.get("confirmed_by")
        if not isinstance(confirmed_raw, dict):
            raise AdapterError(f"{path}/confirmed_by", "missing LONG confirmer")
        result["confirmed_by"] = actual_medium_point(
            confirmed_raw,
            short_by_index,
            short_vertices,
            f"{path}/confirmed_by",
        )
    return result


def mismatch(path: str, oracle: object, project: object, explanation: str) -> Json:
    return {
        "explanation": explanation,
        "oracle": jsonable(oracle),
        "path": path,
        "project": jsonable(project),
    }


def differences(expected: object, actual: object, path: str = "") -> list[Json]:
    if type(expected) is not type(actual):
        return [mismatch(path or "/", expected, actual, "value types differ")]
    if isinstance(expected, dict):
        result = []
        keys = sorted(set(expected) | set(actual))
        for key in keys:
            child = f"{path}/{key}"
            if key not in expected:
                result.append(mismatch(child, None, actual[key], "unexpected project field"))
            elif key not in actual:
                result.append(mismatch(child, expected[key], None, "missing project field"))
            else:
                result.extend(differences(expected[key], actual[key], child))
        return result
    if isinstance(expected, list):
        result = []
        if len(expected) != len(actual):
            result.append(mismatch(path, len(expected), len(actual), "ordered lengths differ"))
        for index, (left, right) in enumerate(zip(expected, actual)):
            result.extend(differences(left, right, f"{path}/{index}"))
        return result
    if expected != actual:
        return [mismatch(path, expected, actual, "exact values differ")]
    return []


def make_check(name: str, expected: object, actual: object, adapter: str) -> Json:
    found = differences(expected, actual, f"/{name.replace('.', '/')}")
    return {
        "adapter": adapter,
        "mismatch_count": len(found),
        "mismatches": found,
        "name": name,
        "passed": not found,
    }


def compare_payloads(
    source_rows: list[Json],
    isolated: Json,
    short: Json,
    medium: Json,
    long: Json,
    project: Json,
) -> list[Json]:
    try:
        hierarchy = project["analysis"]["hierarchy"]
        expected_isolated = [
            expected_isolated_point(item, f"/oracle/isolated/confirmed/{index}")
            for index, item in enumerate(isolated["confirmed"])
        ]
        actual_isolated = [
            actual_isolated_point(
                item,
                source_rows,
                f"/project/isolated/recognitions/{index}",
            )
            for index, item in enumerate(hierarchy["isolated"]["recognitions"])
        ]
        expected_isolated_by_index = {item["index"]: item for item in expected_isolated}
        actual_isolated_by_index = {item["index"]: item for item in actual_isolated}

        expected_short = [
            expected_short_point(item, f"/oracle/short/points/{index}")
            for index, item in enumerate(short["points"])
        ]
        actual_short = [
            actual_short_point(
                item,
                actual_isolated_by_index,
                f"/project/short/points/{index}",
            )
            for index, item in enumerate(hierarchy["short_term"]["points"])
        ]
        expected_short_by_index = {item["index"]: item for item in expected_short}
        actual_short_by_index = {item["index"]: item for item in actual_short}
        expected_short_vertices = [
            expected_short_point(item, f"/oracle/short/vertices/{index}")
            for index, item in enumerate(short["vertices"])
        ]
        actual_short_vertices = [
            actual_short_point(
                item,
                actual_isolated_by_index,
                f"/project/short/vertices/{index}",
            )
            for index, item in enumerate(hierarchy["short_term"]["vertices"])
        ]

        expected_medium = [
            expected_medium_point(
                item,
                expected_short_by_index,
                f"/oracle/medium/points/{index}",
            )
            for index, item in enumerate(medium["points"])
        ]
        actual_medium = [
            actual_medium_point(
                item,
                actual_short_by_index,
                actual_short_vertices,
                f"/project/medium/points/{index}",
            )
            for index, item in enumerate(hierarchy["medium_term"]["points"])
        ]
        expected_medium_by_index = {
            item["pivot"]["index"]: item for item in expected_medium
        }
        actual_medium_by_index = {item["pivot"]["index"]: item for item in actual_medium}
        expected_medium_vertices = [
            expected_medium_point(
                item,
                expected_short_by_index,
                f"/oracle/medium/vertices/{index}",
            )
            for index, item in enumerate(medium["vertices"])
        ]
        actual_medium_vertices = [
            actual_medium_point(
                item,
                actual_short_by_index,
                actual_short_vertices,
                f"/project/medium/vertices/{index}",
            )
            for index, item in enumerate(hierarchy["medium_term"]["vertices"])
        ]

        expected_long = [
            expected_long_point(
                item,
                expected_medium_by_index,
                expected_short_by_index,
                f"/oracle/long/points/{index}",
            )
            for index, item in enumerate(long["points"])
        ]
        actual_long = [
            actual_long_point(
                item,
                actual_medium_by_index,
                actual_medium_vertices,
                actual_short_by_index,
                actual_short_vertices,
                f"/project/long/points/{index}",
            )
            for index, item in enumerate(hierarchy["long_term"]["points"])
        ]

        expected_source = [
            {
                "timestamp": row["timestamp"],
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
            }
            for row in source_rows
        ]
        actual_source = []
        for index, item in enumerate(project["analysis"]["candles"]):
            observation = item["observation"]
            actual_source.append(
                {
                    "timestamp": source_clock(
                        observation.get("timestamp"),
                        f"/project/analysis/candles/{index}/observation/timestamp",
                    ),
                    "open": decimal(observation.get("open"), f"/project/source/{index}/open"),
                    "high": decimal(observation.get("high"), f"/project/source/{index}/high"),
                    "low": decimal(observation.get("low"), f"/project/source/{index}/low"),
                    "close": decimal(observation.get("close"), f"/project/source/{index}/close"),
                }
            )

        expected_short_suppressed = [
            expected_short_suppression(
                item,
                expected_short_by_index,
                f"/oracle/short/suppressed/{index}",
            )
            for index, item in enumerate(short["suppressed"])
        ]
        actual_short_suppressed_stored = [
            {
                "point": actual_short_point(
                    item["point"],
                    actual_isolated_by_index,
                    f"/project/short/suppressed/{index}/point",
                ),
                "reason": canonical_token(
                    item.get("reason"), f"/project/short/suppressed/{index}/reason"
                ),
            }
            for index, item in enumerate(hierarchy["short_term"]["suppressed"])
        ]
        actual_short_suppressed = derive_short_suppression_provenance(actual_short)
        stored_projection = [
            {"point": item["point"], "reason": item["reason"]}
            for item in actual_short_suppressed
        ]
        if actual_short_suppressed_stored != stored_projection:
            raise AdapterError(
                "/project/short/suppressed",
                "stored suppression evidence disagrees with deterministic provenance",
            )

        expected_short_potentials = short.get("potentials")
        if not isinstance(expected_short_potentials, list):
            raise AdapterError(
                "/oracle/short/potentials", "SHORT potentials must be an ordered list"
            )
        actual_short_potentials = hierarchy["short_term"].get("potentials", [])
        if not isinstance(actual_short_potentials, list):
            raise AdapterError(
                "/project/short/potentials", "SHORT potentials must be an ordered list"
            )

        expected_medium_potentials = [
            expected_medium_point(
                item,
                expected_short_by_index,
                f"/oracle/medium/potentials/{index}",
                potential=True,
            )
            for index, item in enumerate(medium["potentials"])
        ]
        actual_medium_potentials = [
            actual_medium_point(
                item,
                actual_short_by_index,
                actual_short_vertices,
                f"/project/medium/potentials/{index}",
                potential=True,
            )
            for index, item in enumerate(hierarchy["medium_term"]["potentials"])
        ]
        expected_medium_suppressed = [
            {
                "point": expected_medium_point(
                    item["point"],
                    expected_short_by_index,
                    f"/oracle/medium/suppressed/{index}/point",
                ),
                "reason": canonical_token(
                    item.get("reason"), f"/oracle/medium/suppressed/{index}/reason"
                ),
            }
            for index, item in enumerate(medium["suppressed"])
        ]
        actual_medium_suppressed = [
            {
                "point": actual_medium_point(
                    item["point"],
                    actual_short_by_index,
                    actual_short_vertices,
                    f"/project/medium/suppressed/{index}/point",
                ),
                "reason": canonical_token(
                    item.get("reason"), f"/project/medium/suppressed/{index}/reason"
                ),
            }
            for index, item in enumerate(hierarchy["medium_term"]["suppressed"])
        ]

        expected_long_potentials = [
            expected_long_point(
                item,
                expected_medium_by_index,
                expected_short_by_index,
                f"/oracle/long/potentials/{index}",
                potential=True,
            )
            for index, item in enumerate(long["potentials"])
        ]
        actual_long_potentials = [
            actual_long_point(
                item,
                actual_medium_by_index,
                actual_medium_vertices,
                actual_short_by_index,
                actual_short_vertices,
                f"/project/long/potentials/{index}",
                potential=True,
            )
            for index, item in enumerate(hierarchy["long_term"]["potentials"])
        ]
        expected_long_vertices = [
            expected_long_point(
                item,
                expected_medium_by_index,
                expected_short_by_index,
                f"/oracle/long/vertices/{index}",
            )
            for index, item in enumerate(long["vertices"])
        ]
        actual_long_vertices = [
            actual_long_point(
                item,
                actual_medium_by_index,
                actual_medium_vertices,
                actual_short_by_index,
                actual_short_vertices,
                f"/project/long/vertices/{index}",
            )
            for index, item in enumerate(hierarchy["long_term"]["vertices"])
        ]
        expected_long_suppressed = [
            {
                "point": expected_long_point(
                    item["point"],
                    expected_medium_by_index,
                    expected_short_by_index,
                    f"/oracle/long/suppressed/{index}/point",
                ),
                "reason": canonical_token(
                    item.get("reason"), f"/oracle/long/suppressed/{index}/reason"
                ),
            }
            for index, item in enumerate(long["suppressed"])
        ]
        actual_long_suppressed = [
            {
                "point": actual_long_point(
                    item["point"],
                    actual_medium_by_index,
                    actual_medium_vertices,
                    actual_short_by_index,
                    actual_short_vertices,
                    f"/project/long/suppressed/{index}/point",
                ),
                "reason": canonical_token(
                    item.get("reason"), f"/project/long/suppressed/{index}/reason"
                ),
            }
            for index, item in enumerate(hierarchy["long_term"]["suppressed"])
        ]

        expected_counts = {
            "isolated_recognitions": len(expected_isolated),
            "isolated_unresolved_potential": int(
                isolated["unresolved_right_edge_potential"] is not None
            ),
            "short_points": len(expected_short),
            "short_vertices": len(expected_short_vertices),
            "short_suppressed": len(expected_short_suppressed),
            "medium_points": len(expected_medium),
            "medium_potentials": len(expected_medium_potentials),
            "medium_vertices": len(expected_medium_vertices),
            "medium_suppressed": len(expected_medium_suppressed),
            "long_points": len(expected_long),
            "long_potentials": len(expected_long_potentials),
            "long_vertices": len(expected_long_vertices),
            "long_suppressed": len(expected_long_suppressed),
        }
        actual_counts = {
            key: integer(value, f"/project/counts/{key}")
            for key, value in project["counts"].items()
        }

        checks = [
            make_check("source.candles", expected_source, actual_source, "source_clock_and_decimal_ohlc_projection"),
            make_check("isolated.confirmed", expected_isolated, actual_isolated, "isolated_direct_projection"),
            make_check("isolated.unresolved", expected_unresolved(isolated["unresolved_right_edge_potential"], "/oracle/isolated/unresolved"), actual_unresolved(hierarchy["isolated"]["unresolved_potential"], source_rows, "/project/isolated/unresolved"), "isolated_right_edge_projection"),
            make_check("short.points", expected_short, actual_short, "short_confirmation_join_projection"),
            make_check("short.vertices", expected_short_vertices, actual_short_vertices, "short_confirmation_join_projection"),
            make_check("short.potentials", expected_short_potentials, actual_short_potentials, "short_no_potential_projection"),
            make_check("short.suppressed", expected_short_suppressed, actual_short_suppressed, "short_suppression_provenance_projection"),
            make_check("medium.points", expected_medium, actual_medium, "medium_canonical_short_vertex_projection"),
            make_check("medium.potentials", expected_medium_potentials, actual_medium_potentials, "medium_canonical_short_vertex_projection"),
            make_check("medium.vertices", expected_medium_vertices, actual_medium_vertices, "medium_canonical_short_vertex_projection"),
            make_check("medium.suppressed", expected_medium_suppressed, actual_medium_suppressed, "suppression_projection"),
            make_check("long.points", expected_long, actual_long, "long_canonical_medium_vertex_projection"),
            make_check("long.potentials", expected_long_potentials, actual_long_potentials, "long_canonical_medium_vertex_projection"),
            make_check("long.vertices", expected_long_vertices, actual_long_vertices, "long_canonical_medium_vertex_projection"),
            make_check("long.suppressed", expected_long_suppressed, actual_long_suppressed, "suppression_projection"),
            make_check("hierarchy.counts", expected_counts, actual_counts, "direct_count_projection"),
        ]

        geometry_expected = [
            point["price"]
            for point in expected_short
        ]
        geometry_actual = [
            source_rows[point["index"]]["high" if point["kind"] == "HIGH" else "low"]
            for point in actual_short
        ]
        checks.append(make_check("source.structural_geometry", geometry_expected, geometry_actual, "canonical_point_source_geometry_projection"))
        return checks
    except (AdapterError, KeyError, IndexError, TypeError) as error:
        path = error.path if isinstance(error, AdapterError) else "/adapter"
        return [
            {
                "adapter": "schema_validation",
                "mismatch_count": 1,
                "mismatches": [
                    mismatch(path, "valid semantic schema", type(error).__name__, str(error))
                ],
                "name": "adapter.schema",
                "passed": False,
            }
        ]


def outcome(checks: list[Json]) -> tuple[str, int]:
    mismatch_count = sum(check["mismatch_count"] for check in checks)
    return ("EXACT_MATCH" if mismatch_count == 0 else "MISMATCH", mismatch_count)


def mutate_short_index(payload: Json) -> None:
    payload["analysis"]["hierarchy"]["short_term"]["vertices"][0]["index"] += 10_000


def mutate_confirmed_by(payload: Json) -> None:
    payload["analysis"]["hierarchy"]["medium_term"]["points"][0]["confirmed_by"]["index"] += 1


def mutate_order(payload: Json) -> None:
    vertices = payload["analysis"]["hierarchy"]["short_term"]["vertices"]
    vertices[0], vertices[1] = vertices[1], vertices[0]


def mutate_ohlc(payload: Json) -> None:
    payload["analysis"]["candles"][0]["observation"]["high"] += Decimal("0.25")


def mutate_missing_status(payload: Json) -> None:
    del payload["analysis"]["hierarchy"]["isolated"]["recognitions"][0]["point"]["status"]


def mutate_representation_only(payload: Json) -> None:
    recognition = payload["analysis"]["hierarchy"]["isolated"]["recognitions"][0]
    recognition["basis"] = recognition["basis"].upper()
    recognition["point"]["kind"] = recognition["point"]["kind"].upper()
    recognition["point"]["status"] = recognition["point"]["status"].upper()


def mutate_short_suppression_provenance(payload: Json) -> None:
    item = next(
        value for value in payload["suppressed"] if "retained_vertex" in value
    )
    item["retained_vertex"]["index"] += 10_000


def mutate_short_potential(payload: Json) -> None:
    payload["potentials"].append(deepcopy(payload["points"][0]))


def run_negative_controls(
    source_rows: list[Json],
    oracle_payloads: tuple[Json, Json, Json, Json],
    project: Json,
) -> list[Json]:
    controls: list[tuple[str, str, Callable[[Json], None], str]] = [
        ("short_vertex_source_index", "project", mutate_short_index, "MISMATCH"),
        ("confirmed_by_provenance", "project", mutate_confirmed_by, "MISMATCH"),
        ("ordered_vertex_reordering", "project", mutate_order, "MISMATCH"),
        ("one_tick_source_geometry", "project", mutate_ohlc, "MISMATCH"),
        ("missing_status", "project", mutate_missing_status, "MISMATCH"),
        ("enum_casing_representation_only", "project", mutate_representation_only, "EXACT_MATCH"),
        ("short_suppression_provenance", "short", mutate_short_suppression_provenance, "MISMATCH"),
        ("short_potential_injection", "short", mutate_short_potential, "MISMATCH"),
    ]
    results = []
    with tempfile.TemporaryDirectory(prefix="mnq-5m-negative-controls-") as directory:
        root = Path(directory)
        for name, target, mutate, expected in controls:
            candidate = deepcopy(project)
            candidate_oracles = deepcopy(oracle_payloads)
            if target == "project":
                mutate(candidate)
            else:
                mutate(candidate_oracles[1])
            path = root / f"{name}.json"
            if target == "project":
                path.write_bytes(mutation_bytes(candidate))
                candidate = load_json(path)
            else:
                path.write_bytes(mutation_bytes(candidate_oracles[1]))
                candidate_oracles = (
                    candidate_oracles[0],
                    load_json(path),
                    candidate_oracles[2],
                    candidate_oracles[3],
                )
            checks = compare_payloads(source_rows, *candidate_oracles, candidate)
            actual, count = outcome(checks)
            first = next(
                (
                    check["mismatches"][0]
                    for check in checks
                    if check["mismatches"]
                ),
                None,
            )
            passed = actual == expected
            results.append(
                {
                    "actual_result": actual,
                    "expected_result": expected,
                    "first_mismatch": first,
                    "name": name,
                    "passed": passed,
                }
            )
            if not passed:
                raise RuntimeError(f"negative control {name} returned {actual}")
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--isolated", required=True, type=Path)
    parser.add_argument("--short", required=True, type=Path)
    parser.add_argument("--medium", required=True, type=Path)
    parser.add_argument("--long", required=True, type=Path)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--historical-manifest", required=True, type=Path)
    parser.add_argument("--historical-report", required=True, type=Path)
    parser.add_argument("--manifest-v2", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--oracle-commit", required=True)
    parser.add_argument("--blind-commit", required=True)
    parser.add_argument("--comparison-commit", required=True)
    parser.add_argument("--negative-controls", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_rows = parse_source(args.source)
    payloads = (
        load_json(args.isolated),
        load_json(args.short),
        load_json(args.medium),
        load_json(args.long),
    )
    project = load_json(args.project)
    checks = compare_payloads(source_rows, *payloads, project)
    result, mismatch_count = outcome(checks)
    controls = (
        run_negative_controls(source_rows, payloads, project)
        if args.negative_controls
        else []
    )
    report = {
        "adapter_definitions": {
            "isolated_direct_projection": "Retains index, kind, exact price, source clock, basis, status, and immediate next-candle confirmer.",
            "short_confirmation_join_projection": "Joins by unique source index to canonical isolated evidence and verifies nested kind, exact price, and recognition basis.",
            "short_no_potential_projection": "The canonical SHORT model has no potential collection. The oracle's explicit list and any project list are compared to the required empty ordered representation; missing project storage is the documented schema representation.",
            "short_suppression_provenance_projection": "Compares every stored suppressed point and reason, then deterministically reconstructs the oracle-only retained_vertex or containing_pair plus suppression_event from the project's ordered canonical SHORT points under the approved fixed-left rule.",
            "medium_canonical_short_vertex_projection": "Resolves oracle SHORT references and project nested SHORT points to complete canonical SHORT records; previous same-kind provenance is derived only from ordered canonical SHORT vertices.",
            "long_canonical_medium_vertex_projection": "Resolves LONG pivot through source_vertex and its nested MEDIUM provenance; this deliberately uses source_vertex.confirmed_by rather than the LONG point's own confirmed_by.",
            "representation_only_fields": "Enum casing and the zero-offset technical timestamp suffix are normalized. No ordered identity, price, source clock, basis, status, confirmer, source level, potential, vertex, or suppression semantics are omitted.",
        },
        "artifacts": {
            "blind_result": {"commit": args.blind_commit, "filename": args.project.name, "sha256": sha256(args.project)},
            "historical_manifest": {"filename": args.historical_manifest.name, "sha256": sha256(args.historical_manifest)},
            "historical_report": {"commit": args.comparison_commit, "filename": args.historical_report.name, "sha256": sha256(args.historical_report)},
            "manifest_v2": None if args.manifest_v2 is None else {"filename": args.manifest_v2.name, "sha256": sha256(args.manifest_v2)},
            "oracle": {
                level: {"filename": path.name, "sha256": sha256(path)}
                for level, path in zip(("isolated", "short", "medium", "long"), (args.isolated, args.short, args.medium, args.long))
            },
            "source": {"filename": args.source.name, "sha256": sha256(args.source)},
        },
        "base_main_commit": args.base_sha,
        "checks": checks,
        "counts": project["counts"],
        "historical_evidence": {
            "provable": [
                "oracle commit precedes blind-result commit",
                "frozen oracle and blind-result bytes remain unchanged",
                "the retained comparator reports zero current semantic mismatches",
            ],
            "not_provable": [
                "exact contents or behavior of the deleted historical helper",
                "whether uncommitted production output was ever inspected before the historical oracle commit",
            ],
            "new_v2_evidence": [
                "retained standalone oracle reproducer",
                "external isolated byte-identical oracle reproduction",
                "retained exact order-sensitive comparator",
                "negative mutation controls with stable mismatch paths",
            ],
        },
        "mismatch_count": mismatch_count,
        "negative_controls": controls,
        "oracle_commit": args.oracle_commit,
        "overall_classification": result,
        "schema_version": 2,
        "tool": {"filename": Path(__file__).name, "sha256": sha256(Path(__file__))},
    }
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    args.output.write_bytes(stable_bytes(report))
    print(json.dumps({"overall_classification": result, "mismatch_count": mismatch_count, "negative_controls": controls}, indent=2, sort_keys=True, default=str))
    if result != "EXACT_MATCH":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
