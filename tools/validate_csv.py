from pathlib import Path
from typing import Iterator, Callable, List, Dict
import os
import csv
import re

URL_PATTERN = re.compile(r'https?://', re.IGNORECASE)
PROVIDER_STATUSES = {"active", "acquired", "renamed", "sunset", "retired", "unknown"}

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

def rule_provider_lifecycle(path: Path, rows: List[Dict[str, str]]) -> List[str]:
    """Validate provider lifecycle values when the optional columns are present."""
    if not rows or "providerStatus" not in rows[0]:
        return []

    errors: List[str] = []
    for idx, row in enumerate(rows, start=2):
        status = (row.get("providerStatus") or "").strip()
        parent = (row.get("parentProvider") or "").strip()

        if status and status not in PROVIDER_STATUSES:
            allowed = ", ".join(sorted(PROVIDER_STATUSES))
            errors.append(
                f"{path}: row {idx}: providerStatus '{status}' is invalid; expected one of {allowed}"
            )

        if parent and status not in {"acquired", "renamed"}:
            errors.append(
                f"{path}: row {idx}: parentProvider requires providerStatus=acquired or renamed"
            )

        if status in {"acquired", "renamed"} and not parent:
            errors.append(
                f"{path}: row {idx}: providerStatus={status} requires parentProvider"
            )

    return errors

def provider_parent_reference_errors(root: Path) -> List[str]:
    """Check parentProvider references against provider slugs when the data tree is present."""
    path = root / "references" / "providers" / "providers.csv"
    if not path.exists():
        return []

    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    slugs = {row.get("slug", "").strip() for row in rows if row.get("slug", "").strip()}
    errors: List[str] = []
    for idx, row in enumerate(rows, start=2):
        parent = (row.get("parentProvider") or "").strip()
        if parent and parent not in slugs:
            errors.append(
                f"{path}: row {idx}: parentProvider '{parent}' does not match a provider slug"
            )
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
    validator.add_rule(rule_provider_lifecycle)
    #validator.add_rule(rule_links_must_be_quoted)

    all_errors: List[str] = []

    for csv_file in iter_csv_files(root):
        errors = validator.validate_file(csv_file)
        all_errors.extend(errors)

    all_errors.extend(provider_parent_reference_errors(root))

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
