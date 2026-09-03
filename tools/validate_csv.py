from pathlib import Path
from typing import Iterator, Callable, List, Dict
import os
import csv
import json
import re

URL_PATTERN = re.compile(r'https?://', re.IGNORECASE)

Rule = Callable[[Path, List[Dict[str, str]]], List[str]]

class CSVValidator:
    def __init__(self) -> None:
        self._rules: List[Rule] = []

    def add_rule(self, rule: Rule) -> None:
        self._rules.append(rule)

    def validate_file(self, path: Path) -> List[str]:
        errors: List[str] = []

        try:
            with path.open(newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        except Exception as e:
            return [f"{path}: read error: {e}"]

        for rule in self._rules:
            errors.extend(rule(path, rows))

        return errors

def rule_slug_sorted(path: Path, rows: List[Dict[str, str]]) -> List[str]:
    if not rows:
        return []

    if "slug" not in rows[0]:
        return []

    errors: List[str] = []
    prev = None

    for idx, row in enumerate(rows, start=2):  # header = row 1
        slug = row.get("slug", "")
        if prev is not None and slug < prev:
            errors.append(
                f"{path}: row {idx}: slug ordering violation: '{slug}' must not appear after '{prev}' (ascending order required)"
            )
        prev = slug

    return errors

def looks_like_url(v: str) -> bool:
    return v.startswith("http://") or v.startswith("https://")

def rule_links_must_be_quoted(path: Path, rows: List[Dict[str, str]]) -> List[str]:
    errors: List[str] = []
    delimiter: str = ","

    with path.open(newline="", encoding="utf-8") as f:
        lines = f.readlines()
    
    if not lines:
        return []
    
    for raw_line in lines:
        line = raw_line.rstrip("\r\n")
        parts = line.split(delimiter)
        for i, cell in enumerate(parts):
            cell = cell.strip()
            if (
                not (cell.startswith('"') and cell.endswith('"'))
                and looks_like_url(cell)
            ):
                errors.append(
                    f"{path}: row {lines.index(raw_line) + 1}: column {i + 1}: URL '{cell}' must be quoted"
                )

    return errors

def iter_csv_files(root: Path) -> Iterator[Path]:
    for dirpath, _, filenames in os.walk(root):
        for name in sorted(filenames):
            if name.lower().endswith(".csv"):
                yield Path(dirpath) / name

def main():
    root = Path(".")

    validator = CSVValidator()
    validator.add_rule(rule_slug_sorted)
    validator.add_rule(rule_action_buttons_max_2)
    validator.add_rule(rule_json_array_no_duplicates)
    #validator.add_rule(rule_links_must_be_quoted)

    all_errors: List[str] = []

    for csv_file in iter_csv_files(root):
        errors = validator.validate_file(csv_file)
        all_errors.extend(errors)

    if all_errors:
        print("Validation errors:")
        for err in all_errors:
            print(f"  - {err}")
        exit(1)
    else:
        print("All checks passed.")
        exit(0)


def rule_action_buttons_max_2(path: Path, rows: List[Dict[str, str]]) -> List[str]:
    """actionButtons must have at most 2 entries (Max 2 buttons per Common-Columns)."""
    errors: List[str] = []
    # Find the actionButtons column name (might be actionButtons in some CSVs)
    for idx, row in enumerate(rows, start=2):
        ab = row.get("actionButtons", "")
        if not ab:
            continue
        try:
            # Parse as JSON array
            buttons = json.loads(ab) if ab.strip().startswith("[") else []
        except (json.JSONDecodeError, ValueError):
            continue
        if len(buttons) > 2:
            errors.append(
                f"{path}: row {idx}: actionButtons has {len(buttons)} entries (max 2): slug='{row.get('slug','')}'"
            )
    return errors


def rule_json_array_no_duplicates(path: Path, rows: List[Dict[str, str]]) -> List[str]:
    """Reject cells that parse as JSON arrays with exact duplicate elements."""
    errors: List[str] = []
    for idx, row in enumerate(rows, start=2):
        for col, val in row.items():
            if not val or not val.strip():
                continue
            s = val.strip()
            if not s.startswith("["):
                continue
            try:
                arr = json.loads(s)
            except (json.JSONDecodeError, ValueError):
                continue
            if not isinstance(arr, list):
                continue
            seen: set = set()
            for item in arr:
                key = repr(item)
                if key in seen:
                    errors.append(
                        f"{path}: row {idx}: column {col}: duplicate JSON-array element {key!r}"
                    )
                    break
                seen.add(key)
    return errors


if __name__ == "__main__":
    main()
