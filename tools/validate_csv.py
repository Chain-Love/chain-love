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


PACKAGE_REGISTRY_ENUM = {
    "npm", "pypi", "crates_io", "maven", "nuget", "go_module",
    "packagist", "rubygems", "hex", "jsr",
}


def rule_packageIdentifiers(path: Path, rows: List[Dict[str, str]]) -> List[str]:
    """DBIP #2507: packageIdentifiers must be a JSON object of registry arrays.

    Values are normalized install identifiers for the SDK itself. Each key
    must be a supported registry/ecosystem; each value a non-empty array of
    unique, non-empty identifier strings. Blank/null cells are allowed (no
    verified identifier yet).
    """
    errors: List[str] = []
    if not rows or "packageIdentifiers" not in rows[0]:
        return errors
    for idx, row in enumerate(rows, start=2):
        raw = (row.get("packageIdentifiers") or "").strip()
        if not raw:
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            errors.append(f"{path}: row {idx}: slug '{row.get('slug', '')}': packageIdentifiers is not valid JSON (got '{raw}')")
            continue
        if not isinstance(value, dict):
            errors.append(f"{path}: row {idx}: slug '{row.get('slug', '')}': packageIdentifiers must be a JSON object (got '{raw}')")
            continue
        if not value:
            errors.append(f"{path}: row {idx}: slug '{row.get('slug', '')}': packageIdentifiers must not be an empty object")
            continue
        for key, ids in value.items():
            if key not in PACKAGE_REGISTRY_ENUM:
                errors.append(f"{path}: row {idx}: slug '{row.get('slug', '')}': invalid registry key '{key}' (allowed: {sorted(PACKAGE_REGISTRY_ENUM)})")
            if not isinstance(ids, list) or not ids:
                errors.append(f"{path}: row {idx}: slug '{row.get('slug', '')}': '{key}' must be a non-empty array")
                continue
            if len(set(ids)) != len(ids):
                errors.append(f"{path}: row {idx}: slug '{row.get('slug', '')}': '{key}' identifiers must be unique")
            for ident in ids:
                if not isinstance(ident, str) or not ident.strip():
                    errors.append(f"{path}: row {idx}: slug '{row.get('slug', '')}': '{key}' identifier must be a non-empty string")
    return errors

def main():
    root = Path(".")

    validator = CSVValidator()
    validator.add_rule(rule_slug_sorted)
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
