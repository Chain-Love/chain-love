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


def rule_offer_provider_slug(path: Path, rows: List[Dict[str, str]]) -> List[str]:
    """Require canonical offer rows to reference one provider slug exactly."""
    if path.parent.name != "offers" or path.parent.parent.name != "references":
        return []

    errors: List[str] = []
    if not rows:
        return errors

    if "provider" in rows[0]:
        errors.append(
            f"{path}: canonical offer tables must use 'providerSlug', not 'provider'"
        )
    if "providerSlug" not in rows[0]:
        errors.append(f"{path}: canonical offer table is missing 'providerSlug'")
        return errors

    providers_path = path.parent.parent / "providers" / "providers.csv"
    if not providers_path.exists():
        return [f"{path}: provider registry not found at {providers_path}"]

    with providers_path.open(newline="", encoding="utf-8") as f:
        provider_rows = list(csv.DictReader(f))

    provider_slugs = set()
    for provider_row_number, provider in enumerate(provider_rows, start=2):
        slug = (provider.get("slug") or "").strip()
        if not slug:
            errors.append(f"{providers_path}: row {provider_row_number} has an empty slug")
        elif slug in provider_slugs:
            errors.append(
                f"{providers_path}: row {provider_row_number} duplicates provider slug '{slug}'"
            )
        provider_slugs.add(slug)

    for row_number, row in enumerate(rows, start=2):
        slug = (row.get("providerSlug") or "").strip()
        if not slug:
            errors.append(f"{path}: row {row_number} has an empty providerSlug")
        elif slug not in provider_slugs:
            errors.append(
                f"{path}: row {row_number} references unknown providerSlug '{slug}'"
            )

    return errors

def main():
    root = Path(".")

    validator = CSVValidator()
    validator.add_rule(rule_slug_sorted)
    validator.add_rule(rule_offer_provider_slug)
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
