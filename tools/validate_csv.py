from pathlib import Path
from typing import Iterator, Callable, List, Dict
import os
import csv
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

def rule_links_must_be_quoted(path: Path, rows: List[Dict[str, str]]) -> List[str]:
    errors: List[str] = []

    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except Exception as e:
        return [f"{path}: read error during link quoting validation: {e}"]

    if not raw_lines:
        return []

    for lineno, raw_line in enumerate(raw_lines, start=1):
        # Parse properly using CSV parser
        parsed_fields = next(csv.reader([raw_line]))

        cursor = 0
        for field in parsed_fields:
            field_stripped = field.strip()

            # Locate this field in the raw line
            # We search from current cursor forward
            idx = raw_line.find(field, cursor)
            if idx == -1:
                continue

            # Determine if it was quoted
            was_quoted = (
                idx > 0
                and idx + len(field) < len(raw_line)
                and raw_line[idx - 1] == '"'
                and raw_line[idx + len(field)] == '"'
            )

            if field_stripped and URL_PATTERN.search(field_stripped):
                if not was_quoted:
                    errors.append(
                        f"{path}: row {lineno}: URL field must be quoted: {field_stripped}"
                    )

            cursor = idx + len(field)

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
    validator.add_rule(rule_links_must_be_quoted)

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
