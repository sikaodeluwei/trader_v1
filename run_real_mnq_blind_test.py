from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from trading.analysis.models import ClosedCandleObservation, OfflineMarketWindow
from trading.analysis.offline import analyze_market_window

EXPECTED_GIT_SHA = "3d0f20fa5752e069842f22941030f62f0edf093e"
EXPECTED_SOURCE_SHA256 = "78eabcf5b2d753311a89a2412e2c277fa51af6f57fe29424ee3363fcb1188e03"

INPUT_FILE = Path("MNQ_2026-09-04_1151-1600_250bars.txt")
OUTPUT_FILE = Path("MNQ_2026-09-04_1151-1600_project_blind_result.json")


def run_git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args],
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()


def verify_repo() -> str:
    head = run_git("rev-parse", "HEAD")
    if head != EXPECTED_GIT_SHA:
        raise SystemExit(
            f"STOP: repo HEAD is {head}, expected {EXPECTED_GIT_SHA}"
        )

    # Ignore untracked runner/input/output artifacts; require tracked files unchanged.
    subprocess.run(["git", "diff", "--quiet"], check=True)
    subprocess.run(["git", "diff", "--cached", "--quiet"], check=True)
    return head


def source_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_ninjatrader_rows(path: Path) -> tuple[ClosedCandleObservation, ...]:
    raw_lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(raw_lines) != 250:
        raise SystemExit(f"STOP: expected exactly 250 rows, found {len(raw_lines)}")

    candles: list[ClosedCandleObservation] = []
    for row_number, line in enumerate(raw_lines, start=1):
        parts = line.split(";")
        if len(parts) != 6:
            raise SystemExit(
                f"STOP: row {row_number} has {len(parts)} fields, expected 6"
            )

        timestamp_text, open_text, high_text, low_text, close_text, _volume_text = parts

        # Neutral technical timezone marker only.
        # Clock values are NOT shifted.
        timestamp = datetime.strptime(
            timestamp_text, "%Y%m%d %H%M%S"
        ).replace(tzinfo=timezone.utc)

        candles.append(
            ClosedCandleObservation(
                timestamp=timestamp,
                open=float(open_text),
                high=float(high_text),
                low=float(low_text),
                close=float(close_text),
                intrabar_prices=None,
            )
        )

    return tuple(candles)


def encode(value):
    if is_dataclass(value):
        return {field.name: encode(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, tuple):
        return [encode(item) for item in value]
    if isinstance(value, list):
        return [encode(item) for item in value]
    if isinstance(value, dict):
        return {str(key): encode(item) for key, item in value.items()}
    return value


def main() -> None:
    head = verify_repo()

    if not INPUT_FILE.exists():
        raise SystemExit(
            f"STOP: {INPUT_FILE.name} is not in the current repo folder"
        )

    source_hash = source_sha256(INPUT_FILE)
    if source_hash != EXPECTED_SOURCE_SHA256:
        raise SystemExit(
            "STOP: source SHA-256 mismatch\n"
            f"actual:   {source_hash}\n"
            f"expected: {EXPECTED_SOURCE_SHA256}"
        )

    candles = load_ninjatrader_rows(INPUT_FILE)

    window = OfflineMarketWindow(
        instrument="MNQ 09-26",
        timeframe="1 minute",
        start_index=0,
        candles=candles,
    )

    # Actual production analyzer call.
    # No ground truth is loaded anywhere in this runner.
    result = analyze_market_window(window, segment=None)

    hierarchy = result.hierarchy
    payload = {
        "metadata": {
            "analyzer_git_sha": head,
            "source_filename": INPUT_FILE.name,
            "source_sha256": source_hash,
            "instrument": window.instrument,
            "timeframe": window.timeframe,
            "bar_count": len(window.candles),
            "start_index": window.start_index,
            "first_timestamp": window.candles[0].timestamp.isoformat(),
            "last_timestamp": window.candles[-1].timestamp.isoformat(),
            "timezone_note": (
                "UTC attached only as a neutral technical timezone marker; "
                "original NinjaTrader clock values were not shifted."
            ),
            "segment_requested": False,
        },
        "counts": {
            "isolated_recognitions": len(hierarchy.isolated.recognitions),
            "isolated_unresolved_potential": (
                0 if hierarchy.isolated.unresolved_potential is None else 1
            ),
            "short_points": len(hierarchy.short_term.points),
            "short_vertices": len(hierarchy.short_term.vertices),
            "short_suppressed": len(hierarchy.short_term.suppressed),
            "medium_points": len(hierarchy.medium_term.points),
            "medium_potentials": len(hierarchy.medium_term.potentials),
            "medium_vertices": len(hierarchy.medium_term.vertices),
            "medium_suppressed": len(hierarchy.medium_term.suppressed),
            "long_points": len(hierarchy.long_term.points),
            "long_potentials": len(hierarchy.long_term.potentials),
            "long_vertices": len(hierarchy.long_term.vertices),
            "long_suppressed": len(hierarchy.long_term.suppressed),
        },
        "analysis": encode(result),
    }

    OUTPUT_FILE.write_text(
        json.dumps(payload, indent=2, sort_keys=False),
        encoding="utf-8",
    )

    # Confirm the source file did not change during the run.
    final_source_hash = source_sha256(INPUT_FILE)
    if final_source_hash != EXPECTED_SOURCE_SHA256:
        raise SystemExit("STOP: source file changed during the run")

    # Confirm tracked repository code/tests remain unchanged.
    subprocess.run(["git", "diff", "--quiet"], check=True)
    subprocess.run(["git", "diff", "--cached", "--quiet"], check=True)

    print("REAL BLIND ANALYZER RUN COMPLETE")
    print(f"Git SHA: {head}")
    print(f"Source SHA-256: {source_hash}")
    print(f"Rows: {len(candles)}")
    print(f"Output: {OUTPUT_FILE.resolve()}")
    print(json.dumps(payload["counts"], indent=2))
    print(
        "Unresolved isolated potential:",
        "NONE" if hierarchy.isolated.unresolved_potential is None else
        encode(hierarchy.isolated.unresolved_potential),
    )
    print("Segment/BMS/SMS run: NO")
    print("Ground truth loaded: NO")
    print("Tracked repo changes: NO")


if __name__ == "__main__":
    main()
