#!/usr/bin/env python3
"""Normalize faucet dripLimitAmount/dripLimitPeriod into dripLimits JSON.

WHY: The current free-text columns mix quantities, asset symbols, prose,
multiple tiers, missing units, and literal null sentinels. This script
normalizes them into a structured JSON array that can be validated and
compared reliably.
"""

import csv
import json
import re
import sys
from typing import Any, Dict, List, Optional, Tuple


# Period string to seconds mapping
PERIOD_MAP = {
    "sec": 1,
    "s": 1,
    "min": 60,
    "m": 60,
    "h": 3600,
    "hr": 3600,
    "d": 86400,
    "day": 86400,
    "w": 604800,
    "week": 604800,
}

# Default asset when amount is numeric but no asset specified
DEFAULT_ASSET = "ETH"


def parse_period(period_str: str) -> Optional[int]:
    """Convert a period string to seconds.

    WHY: Period values are inconsistent across the dataset. This function
    handles all known formats: '24h', '10sec', '0.1' (hours), bare numbers.

    Returns None if period is empty or unparseable.
    """
    if not period_str or period_str.strip().upper() == "NULL":
        return None

    period_str = period_str.strip().lower()

    # Try "Nunit" format (e.g., "24h", "10sec", "30min")
    match = re.match(r"^(\d+(?:\.\d+)?)\s*(sec|s|min|m|h|hr|d|day|w|week)s?$", period_str)
    if match:
        value = float(match.group(1))
        unit = match.group(2)
        return int(value * PERIOD_MAP.get(unit, 3600))

    # Try bare number (assume hours)
    try:
        value = float(period_str)
        return int(value * 3600)
    except ValueError:
        return None


def parse_amount_and_asset(amount_str: str) -> List[Tuple[str, str, Optional[str]]]:
    """Parse amount string into (amount, asset, condition) tuples.

    WHY: Amount values are highly inconsistent. This handles:
    - Simple: "0.1 ETH" -> [("0.1", "ETH", None)]
    - Multi-tier: "0.5/1/2.5/5 SOL" -> [("0.5","SOL"), ("1","SOL"), ...]
    - Compound: "0.1 ETH/1 ETH72h" -> [("0.1","ETH"), ("1","ETH")]
    - Qualifiers: "up to 1 TON" -> [("1", "TON", "maximum")]
    - Bare numbers: "0.001" -> [("0.001", "ETH", None)]
    """
    if not amount_str or amount_str.strip().upper() == "NULL":
        return []

    amount_str = amount_str.strip()

    # Handle "up to N ASSET" pattern
    up_to_match = re.match(r"up to\s+(\d+(?:\.\d+)?)\s*([A-Za-z0-9]+)", amount_str, re.IGNORECASE)
    if up_to_match:
        return [(up_to_match.group(1), up_to_match.group(2).upper(), "maximum")]

    # Handle multi-tier "N/M/P ASSET" pattern (shared asset at end)
    multi_match = re.match(r"^([\d./\s]+)\s+([A-Za-z][A-Za-z0-9]*)$", amount_str, re.IGNORECASE)
    if multi_match:
        amounts_str = multi_match.group(1).strip()
        asset = multi_match.group(2).upper()
        amounts = [a.strip() for a in amounts_str.split("/") if a.strip()]
        return [(a, asset, None) for a in amounts]

    # Handle compound "N ASSET/M ASSET2" pattern (each part has its own asset)
    if "/" in amount_str:
        parts = amount_str.split("/")
        compound_results: List[Tuple[str, str, Optional[str]]] = []
        for part in parts:
            part = part.strip()
            # Try "N ASSET" format (asset must start with letter)
            match = re.match(r"(\d+(?:\.\d+)?)\s+([A-Za-z][A-Za-z0-9]*)", part, re.IGNORECASE)
            if match:
                compound_results.append((str(match.group(1)), str(match.group(2).upper()), None))
            else:
                # Try bare number (no asset)
                try:
                    val = float(part)
                    compound_results.append((str(val), DEFAULT_ASSET, None))
                except ValueError:
                    pass
        return compound_results if compound_results else []

    # Simple "N ASSET" format (asset must start with letter)
    match = re.match(r"(\d+(?:\.\d+)?)\s+([A-Za-z][A-Za-z0-9]*)", amount_str, re.IGNORECASE)
    if match:
        return [(match.group(1), match.group(2).upper(), None)]

    # Bare number
    try:
        float(amount_str)
        return [(amount_str, DEFAULT_ASSET, None)]
    except ValueError:
        return []


def normalize_faucet_row(row: Dict[str, str]) -> Optional[str]:
    """Transform a single faucet row's amount/period into dripLimits JSON.

    WHY: Each row may have different formats. This function applies the
    full normalization pipeline and returns the JSON string for the
    dripLimits column.
    """
    amount_str = row.get("dripLimitAmount", "").strip()
    period_str = row.get("dripLimitPeriod", "").strip()

    # Skip if both empty
    if not amount_str and not period_str:
        return ""

    # Parse period
    cooldown = parse_period(period_str)

    # Parse amounts
    amounts = parse_amount_and_asset(amount_str)

    # If no amounts but period exists, skip (can't have cooldown without amount)
    if not amounts:
        return ""

    # Build dripLimits array
    drip_limits = []
    for amount, asset, condition in amounts:
        entry: Dict[str, Any] = {"amount": amount, "asset": asset}
        if cooldown is not None:
            entry["cooldownSeconds"] = cooldown
        if condition:
            entry["condition"] = condition
        drip_limits.append(entry)

    return json.dumps(drip_limits, separators=(",", ":"))


def normalize_csv(input_path: str, output_path: Optional[str] = None) -> None:
    """Read faucets.csv, add dripLimits column, write output.

    WHY: Preserves all existing columns while adding the new normalized
    column. The legacy columns are kept for backward compatibility.
    """
    if output_path is None:
        output_path = input_path

    with open(input_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    # Add dripLimits to fieldnames if not present
    if "dripLimits" not in fieldnames:
        fieldnames = list(fieldnames) + ["dripLimits"]

    # Process rows
    for row in rows:
        row["dripLimits"] = normalize_faucet_row(row)

    # Write output
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Processed {len(rows)} rows -> {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <input.csv> [output.csv]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    normalize_csv(input_file, output_file)
