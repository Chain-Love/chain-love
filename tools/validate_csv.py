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


COUNTRY_MODE_ENUM = {"globalExceptExcluded", "explicitAllowlist", "providerDefined", "unknown"}


def rule_countryAvailability(path: Path, rows: List[Dict[str, str]]) -> List[str]:
    """DBIP #2485: ramps country availability normalization.

    - countryAvailabilityMode must be one of the four enum values.
    - supportedCountries must be a JSON array of uppercase ISO 3166-1 alpha-2
      codes, unique and A-Z sorted; should be empty unless mode is explicitAllowlist.
    - A country code may not appear in both supportedCountries and bannedCountries.
    """
    errors: List[str] = []
    if not rows or "countryAvailabilityMode" not in rows[0]:
        return errors
    use_mode = "countryAvailabilityMode" in rows[0]
    use_sup = "supportedCountries" in rows[0]
    use_ban = "bannedCountries" in rows[0]
    for idx, row in enumerate(rows, start=2):
        slug = row.get("slug", "")
        mode = (row.get("countryAvailabilityMode") or "").strip()
        if use_mode and mode and mode not in COUNTRY_MODE_ENUM:
            errors.append(f"{path}: row {idx}: slug '{slug}': invalid countryAvailabilityMode '{mode}' (allowed: {sorted(COUNTRY_MODE_ENUM)})")
        sup_raw = (row.get("supportedCountries") or "").strip()
        sup = []
        if sup_raw:
            try:
                sup = json.loads(sup_raw)
            except json.JSONDecodeError:
                errors.append(f"{path}: row {idx}: slug '{slug}': supportedCountries is not valid JSON (got '{sup_raw}')")
                continue
            if not isinstance(sup, list):
                errors.append(f"{path}: row {idx}: slug '{slug}': supportedCountries must be a JSON array")
                continue
            for code in sup:
                if not isinstance(code, str) or len(code) != 2 or not code.isupper() or not code.isalpha():
                    errors.append(f"{path}: row {idx}: slug '{slug}': invalid ISO code '{code}' in supportedCountries (uppercase alpha-2 required)")
            if len(set(sup)) != len(sup):
                errors.append(f"{path}: row {idx}: slug '{slug}': supportedCountries must not contain duplicates")
            if sup != sorted(sup):
                errors.append(f"{path}: row {idx}: slug '{slug}': supportedCountries must be sorted A-Z")
        if sup and mode == "globalExceptExcluded":
            errors.append(f"{path}: row {idx}: slug '{slug}': supportedCountries must be empty for globalExceptExcluded mode")
        ban_raw = (row.get("bannedCountries") or "").strip()
        if ban_raw and sup_raw:
            try:
                ban = json.loads(ban_raw)
                overlap = set(ban) & set(sup)
                if overlap:
                    errors.append(f"{path}: row {idx}: slug '{slug}': country code(s) {sorted(overlap)} appear in both supportedCountries and bannedCountries")
            except json.JSONDecodeError:
                pass
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
