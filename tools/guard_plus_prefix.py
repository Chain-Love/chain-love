#!/usr/bin/env python3
"""
CSV round-trip guard for '+' prefixed link values (Chain-Love #4602).

Problem
-------
The project recommends that contributors edit CSVs in spreadsheet tools
(CONTRIBUTING.md). Spreadsheets interpret a leading '+' as a formula marker and
silently drop it: `+i6uiSjWwiKxjMTZk` becomes `i6uiSjWwiKxjMTZk`.

In `references/providers/providers.csv` the `telegram` column holds literal
Telegram invite-code prefixes, and 13 rows currently carry a leading '+'. A
spreadsheet round trip would strip them, silently changing the value, and the
schema treats `telegram` as "the value after domain" — so the corrupted form is
indistinguishable from a legitimate one.

What this adds
--------------
A `tools/guard_plus_prefix.py` script, wired into the existing pre-commit hook
(git-hooks/pre-commit.py runs a script list), that:

  1. Scans every CSV in the repo for cells that begin with '+'.
  2. For each one, checks whether it is a *known, intentional* prefix value by
     looking it up in the canonical list of accepted `+` values (see below).
  3. Fails the commit if a '+' value is found that is NOT in the accepted list —
     i.e. one that was introduced by a spreadsheet and has no business being there.
  4. Reports any accepted '+' value that is *missing* from the CSVs, which is the
     actual regression this issue is about: a value that should be present but was
     silently dropped by a round trip.

Why a list and not a blanket ban
--------------------------------
Some '+' values are legitimately part of the data (Telegram invite codes). Banning
all '+' would break those rows. The accepted list records exactly which cells are
supposed to carry a '+', so the guard distinguishes "intended prefix" from
"spreadsheet damage".
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Cells that are KNOWN to legitimately begin with '+'. Anything else beginning with
# '+' is treated as spreadsheet damage and fails the check.
#
# Keyed by (relative csv path, column name) -> set of accepted '+' values.
ACCEPTED_PLUS: dict[tuple[str, str], set[str]] = {
    ("references/providers/providers.csv", "telegram"): {
        "+i6uiSjWwiKxjMTZk",
        "+x9IHkcVqcxcyNjVk",
        "+GXmteLocFPs5ZWY8",
        "+lI4ee8w4y3U2NWM1",
        "+Xj6_zTPfcUA4MGQ1",
        "+nQV508SoBgliNzA0",
        "+5CtF7wTbAJVhODgx",
        "+Stx-wLOdj49iNDM0",
        "+elnozTFe3OY0NDA1",
        "+s_oRMnGpOyQ3ODQ0",
        "+ldEA4oysskNiMzE1",
        "+ANThR9bHDLAwMjUx",
        "+Kf2WwC0VmxkxNzY1",
    },
}


def read_rows(path: Path) -> list[dict[str, str]]:
    """Read a CSV preserving the raw cell text (no type coercion)."""
    with path.open("r", newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def check_file(rel: str, path: Path) -> list[str]:
    """Return a list of problems for one CSV file."""
    problems: list[str] = []
    accepted_map = {col: vals for (csv, col), vals in ACCEPTED_PLUS.items() if csv == rel}
    if not accepted_map:
        # No '+' expected in this file: any leading '+' is damage.
        if not path.exists():
            return problems
        for i, row in enumerate(read_rows(path), start=2):
            for col, val in row.items():
                if val and val.startswith("+"):
                    problems.append(
                        f"{rel}:{i} column '{col}' begins with '+' but this file "
                        f"declares no accepted '+' values: {val!r}"
                    )
        return problems

    rows = read_rows(path) if path.exists() else []
    seen: dict[str, set[str]] = {col: set() for col in accepted_map}

    for i, row in enumerate(rows, start=2):
        for col, accepted in accepted_map.items():
            val = (row.get(col) or "").strip()
            if not val:
                continue
            if val.startswith("+"):
                if val in accepted:
                    seen[col].add(val)
                else:
                    problems.append(
                        f"{rel}:{i} column '{col}' has unexpected '+' value {val!r} "
                        f"(spreadsheet round-trip damage?)"
                    )
            elif val in accepted:
                # The accepted value exists but WITHOUT the '+' — the exact
                # regression: a spreadsheet stripped the prefix.
                problems.append(
                    f"{rel}:{i} column '{col}' lost its leading '+' on {val!r}; "
                    f"expected {accepted_map[col] and ('+' + val)!r}"
                )

    # Accepted values that vanished entirely.
    for col, accepted in accepted_map.items():
        missing = accepted - seen[col]
        if missing:
            problems.append(
                f"{rel} column '{col}': {len(missing)} accepted '+' value(s) missing "
                f"from the CSV (stripped by a round trip?): {sorted(missing)}"
            )
    return problems


def main() -> int:
    problems: list[str] = []
    checked = 0

    for (rel, _col) in ACCEPTED_PLUS:
        path = REPO_ROOT / rel
        if not path.exists():
            problems.append(f"{rel}: file not found")
            continue
        checked += 1
        problems.extend(check_file(rel, path))

    # Also scan for stray '+' in files that declare none.
    for csv_path in sorted(REPO_ROOT.rglob("*.csv")):
        if ".git" in csv_path.parts:
            continue
        rel = csv_path.relative_to(REPO_ROOT).as_posix()
        if rel in {r for r, _ in ACCEPTED_PLUS}:
            continue
        checked += 1
        problems.extend(check_file(rel, csv_path))

    if problems:
        print("CSV '+' prefix guard failed:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        print(
            "\nA spreadsheet round trip stripped a leading '+' (or introduced one). "
            "Edit the CSV as plain text, or add the value to ACCEPTED_PLUS in "
            "tools/guard_plus_prefix.py if it is legitimately a prefix.",
            file=sys.stderr,
        )
        return 1

    print(f"CSV '+' prefix guard passed ({checked} file(s) checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
