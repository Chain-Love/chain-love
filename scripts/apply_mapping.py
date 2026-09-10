#!/usr/bin/env python3
"""
apply_mapping.py — Apply canonical mapping to sdkLanguages column.
"""

import csv
import json
import os
import sys
from pathlib import Path
import glob

NORMALIZE_MAP = {
    "TypeScript SDK": "TypeScript",
    "JavaScript SDK": "JavaScript",
    "JS SDK": "JavaScript",
    "Node.JS SDK": "Node.js",
    "PancakeSwap SDK": "JavaScript",
    "Python SDK": "Python",
    "Relay SDK": None,
    "TypeScript CLI": "TypeScript",
    "Node.JS": "Node.js",
    "CosmJS": "JavaScript",
    "React": "JavaScript",
    "TON Kotlin": "Kotlin",
    "CSS": None,
}

REMOVE_VALUES = {"Web UI", "API", "SDK", "SDK CLI?", "Web UI?"}


def parse_csv_array(cell):
    cell = cell.strip()
    if not cell or cell == "NULL" or cell == '""':
        return None
    try:
        if cell.startswith('"') and cell.endswith('"'):
            cell = cell[1:-1]
        cell = cell.replace('""', '"')
        parsed = json.loads(cell)
        if isinstance(parsed, list):
            return parsed
        return None
    except (json.JSONDecodeError, TypeError):
        return None


def write_csv_array(items):
    if not items:
        return "NULL"
    return json.dumps(items, ensure_ascii=False)


def apply_mapping_to_cell(cell):
    items = parse_csv_array(cell)
    if items is None:
        return cell, False

    original_items = list(items)
    new_items = []
    changes = False

    for item in items:
        item_stripped = item.strip()
        if item_stripped in REMOVE_VALUES:
            changes = True
            continue
        if item_stripped in NORMALIZE_MAP:
            result = NORMALIZE_MAP[item_stripped]
            if result is None:
                changes = True
                continue
            else:
                if result != item_stripped:
                    changes = True
                new_items.append(result)
                continue
        new_items.append(item_stripped)

    seen = set()
    deduped = []
    for item in new_items:
        if item not in seen:
            seen.add(item)
            deduped.append(item)

    if len(deduped) != len(new_items):
        changes = True

    if not deduped:
        return "NULL", True

    if changes:
        return write_csv_array(deduped), True
    return cell, False


def process_file(filepath, col_name):
    with open(filepath, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    if col_name not in fieldnames:
        return 0, len(rows)

    changes = 0
    for row in rows:
        old_val = row.get(col_name, "")
        new_val, changed = apply_mapping_to_cell(old_val)
        if changed:
            row[col_name] = new_val
            changes += 1

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return changes, len(rows)


def main():
    base = Path("/home/samounox/Projects/CYBER_BOUNTY/targets/chain-love")

    ref_files = [
        (base / "references/offers/bridges.csv", "sdkLanguages"),
        (base / "references/offers/explorers.csv", "sdkLanguages"),
        (base / "references/offers/oracles.csv", "sdkLanguages"),
    ]

    listing_files = []
    for f in glob.glob(str(base / "listings/specific-networks/*/*.csv")):
        listing_files.append((f, "sdk"))
    for f in glob.glob(str(base / "listings/all-networks/*.csv")):
        listing_files.append((f, "sdk"))

    total_changes = 0
    total_rows = 0
    files_changed = 0

    print("=== Processing Reference Files ===")
    for filepath, col in ref_files:
        changes, rows = process_file(filepath, col)
        total_changes += changes
        total_rows += rows
        if changes > 0:
            files_changed += 1
            print(f"  {filepath.name}: {changes} cells changed, {rows} rows")
        else:
            print(f"  {filepath.name}: no changes, {rows} rows")

    print("\n=== Processing Listing Files ===")
    for filepath, col in listing_files:
        changes, rows = process_file(filepath, col)
        total_changes += changes
        total_rows += rows
        if changes > 0:
            files_changed += 1
            print(f"  {os.path.relpath(filepath, base)}: {changes} cells changed, {rows} rows")

    print(f"\n=== Summary ===")
    print(f"Files modified: {files_changed}")
    print(f"Total cells changed: {total_changes}")
    print(f"Total rows processed: {total_rows}")


if __name__ == "__main__":
    main()
