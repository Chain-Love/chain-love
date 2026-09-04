#!/usr/bin/env python3
"""DBIP #3597: listing headers must equal the canonical header of
references/offers/<category>.csv, optionally plus the listing-only 'chain'
column at the position in tools/listing_header_exceptions.json.
Non-blocking by default; pass --strict to fail on drift."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

CHAIN = "chain"
EXCEPTIONS = Path(__file__).resolve().parent / "listing_header_exceptions.json"


def read_header(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as f:
        try:
            return next(csv.reader(f))
        except StopIteration:
            return []


def diff_header(canon: list[str], hdr: list[str], chain_pos: int | None) -> str | None:
    has_chain = CHAIN in hdr and chain_pos is not None
    expected = canon[:chain_pos] + [CHAIN] + canon[chain_pos:] if has_chain else canon
    if hdr == expected:
        return None
    if CHAIN in hdr and chain_pos is None:
        return f"'{CHAIN}' present but no position documented for this category"
    dupes = sorted({c for c in hdr if hdr.count(c) > 1})
    if dupes:
        return f"duplicate columns: {dupes}"
    missing = [c for c in expected if c not in hdr]
    extra = [c for c in hdr if c not in expected]
    if missing or extra:
        return "; ".join(p for p in (f"missing {missing}" if missing else "", f"extra {extra}" if extra else "") if p)
    first = next(i for i, (a, b) in enumerate(zip(hdr, expected)) if a != b)
    return f"order mismatch: column {first} is '{hdr[first]}', expected '{expected[first]}'"


def main(root: Path, strict: bool) -> int:
    spec = json.loads(EXCEPTIONS.read_text(encoding="utf-8"))
    positions = {c: s[CHAIN] for c, s in spec.items() if not c.startswith("_") and CHAIN in s}
    canon = {p.stem: read_header(p) for p in sorted((root / "references" / "offers").glob("*.csv"))}
    problems = [f"{l}: {m}" for l in sorted((root / "listings").rglob("*.csv")) if l.stem in canon
                for m in [diff_header(canon[l.stem], read_header(l), positions.get(l.stem))] if m]
    if not problems:
        print("All listing headers match canonical offer schemas.")
        return 0
    print(f"Listing header drift vs canonical offer schemas ({len(problems)} file(s)):")
    for p in problems:
        print(f"  {'ERROR' if strict else 'WARN'} {p}")
    if strict:
        return 1
    print("Non-blocking mode: normalize drift in separate small PRs, then gate with --strict.")
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    sys.exit(main(Path(a[0]) if a and not a[0].startswith("--") else Path("."), "--strict" in a))
