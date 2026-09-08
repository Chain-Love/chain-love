#!/usr/bin/env python3
"""Tests for clear_sdk_tbd.py."""

import csv
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from clear_sdk_tbd import SDK_TBD_COLUMNS, SENTINELS, clear_sdk_tbd  # noqa: E402


def _count_tbd(csv_path: str) -> int:
    """Count TBD/NULL/null cells in SDK columns."""
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            for col in SDK_TBD_COLUMNS:
                val = row.get(col, "").strip()
                if val in SENTINELS:
                    count += 1
    return count


def _count_real(csv_path: str) -> int:
    """Count non-empty, non-sentinel cells in SDK columns."""
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            for col in SDK_TBD_COLUMNS:
                val = row.get(col, "").strip()
                if val and val not in SENTINELS:
                    count += 1
    return count


def test_clear_sdk_tbd_basic(tmp_path: Path) -> None:
    """Clear TBD from a minimal CSV."""
    csv_path = str(tmp_path / "test_sdks.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["slug", "latestKnownVersion", "license"])
        writer.writerow(["test-a", "TBD", "MIT"])
        writer.writerow(["test-b", "1.0.0", "TBD"])

    cleared = clear_sdk_tbd(csv_path)
    assert cleared == 2

    with open(csv_path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert rows[0]["latestKnownVersion"] == ""
    assert rows[0]["license"] == "MIT"
    assert rows[1]["latestKnownVersion"] == "1.0.0"
    assert rows[1]["license"] == ""


def test_preserves_real_values(tmp_path: Path) -> None:
    """Real values must survive the transformation."""
    csv_path = str(tmp_path / "test_sdks.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["slug", "latestKnownVersion", "latestKnownReleaseDate", "maintainer", "license"])
        writer.writerow(["a", "2.1.0", "2026-02-24", "Ava Labs", "Apache-2.0"])
        writer.writerow(["b", "TBD", "TBD", "TBD", "TBD"])

    real_before = _count_real(csv_path)
    clear_sdk_tbd(csv_path)
    real_after = _count_real(csv_path)
    assert real_before == real_after == 4


def test_clears_all_sentinels(tmp_path: Path) -> None:
    """TBD, NULL, and null are all cleared."""
    csv_path = str(tmp_path / "test_sdks.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["slug", "license"])
        writer.writerow(["a", "TBD"])
        writer.writerow(["b", "NULL"])
        writer.writerow(["c", "null"])

    cleared = clear_sdk_tbd(csv_path)
    assert cleared == 3
    assert _count_tbd(csv_path) == 0


def test_real_csv(tmp_path: Path) -> None:
    """Run on a realistic CSV and verify TBD goes to 0."""
    csv_path = str(tmp_path / "sdks.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["slug", "latestKnownVersion", "latestKnownReleaseDate", "maintainer", "license"])
        writer.writerow(["a", "2.1.0", "2026-02-24", "Ava Labs", "Apache-2.0"])
        writer.writerow(["b", "TBD", "TBD", "TBD", "TBD"])
        writer.writerow(["c", "1.0.0", "", "Chainlink", "MIT"])
        writer.writerow(["d", "TBD", "2026-01-01", "TBD", "BSD-3-Clause"])

    tbd_before = _count_tbd(csv_path)
    real_before = _count_real(csv_path)
    assert tbd_before == 6
    assert real_before == 9

    cleared = clear_sdk_tbd(csv_path)
    assert cleared == 6
    assert _count_tbd(csv_path) == 0
    assert _count_real(csv_path) == real_before
