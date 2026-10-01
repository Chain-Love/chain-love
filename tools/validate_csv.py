from pathlib import Path
from typing import Iterator, Callable, List, Dict
import os
import csv
import json
import re
import urllib.parse

URL_PATTERN = re.compile(r'https?://', re.IGNORECASE)
ACTIONBUTTON_MD_LINK = re.compile(r'\[([^\]]*)\]\(([^)]+)\)')

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

def normalize_action_button_destination(dest: str) -> str:
    dest = dest.strip()
    parts = urllib.parse.urlsplit(dest)
    if parts.scheme in ("http", "https"):
        path = parts.path.rstrip("/") or "/"
        return urllib.parse.urlunsplit(
            (parts.scheme.lower(), parts.netloc.lower(), path, parts.query, parts.fragment)
        )
    if parts.scheme == "mailto":
        return dest.lower()
    return dest.rstrip("/")

def rule_actionbuttons_unique_destinations(path: Path, rows: List[Dict[str, str]]) -> List[str]:
    if not rows or "actionButtons" not in rows[0]:
        return []

    errors: List[str] = []

    for idx, row in enumerate(rows, start=2):
        raw = (row.get("actionButtons") or "").strip()
        if not raw:
            continue
        try:
            items = json.loads(raw)
        except Exception:
            continue
        if not isinstance(items, list):
            continue

        slug = row.get("slug", "")
        first_label: Dict[str, str] = {}
        for item in items:
            if not isinstance(item, str):
                continue
            match = ACTIONBUTTON_MD_LINK.search(item)
            if not match:
                continue
            label, dest = match.group(1), match.group(2)
            key = normalize_action_button_destination(dest)
            if key in first_label:
                errors.append(
                    f"{path}: row {idx}: duplicate actionButtons destination ({slug}): "
                    f"{dest} is used by both \"{first_label[key]}\" and \"{label}\""
                )
            else:
                first_label[key] = label

    return errors

def main():
    root = Path(".")

    validator = CSVValidator()
    validator.add_rule(rule_slug_sorted)
    validator.add_rule(rule_actionbuttons_unique_destinations)
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

if __name__ == "__main__":
    main()
