#!/usr/bin/env python3
"""Clear TBD sentinels from SDK reserved columns in sdks.csv.

WHY: Issue #3574 — 4 columns reserved for automation hold 106-120 TBD
sentinels each. Clearing them prepares the data for when the converter
is fixed (PR #3574-B on json-tools).

Columns affected: latestKnownVersion, latestKnownReleaseDate, maintainer, license
Columns NOT affected: verifiedUptime, verifiedLatency, verifiedBlocksBehindAvg (APIs)
"""

import csv
import sys
from typing import List

SDK_TBD_COLUMNS: List[str] = [
    "latestKnownVersion",
    "latestKnownReleaseDate",
    "maintainer",
    "license",
]

SENTINELS = {"TBD", "NULL", "null"}


def clear_sdk_tbd(csv_path: str) -> int:
    """Clear TBD sentinels from SDK columns. Returns count of cells cleared."""
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    cleared = 0
    for row in rows:
        for col in SDK_TBD_COLUMNS:
            if col in fieldnames:
                val = row[col].strip() if row[col] else ""
                if val in SENTINELS:
                    row[col] = ""
                    cleared += 1

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return cleared


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "references/offers/sdks.csv"
    n = clear_sdk_tbd(path)
    print(f"Cleared {n} TBD sentinels from {path}")
