from pathlib import Path
from typing import Iterator, Callable, List, Dict
import os
import csv
import re
import json
import unicodedata

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

def normalize_identity(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(ch for ch in normalized if ch.isalnum())

def rule_provider_aliases(path: Path, rows: List[Dict[str, str]]) -> List[str]:
    """Validate provider aliases and reject ambiguous identity matches."""
    if not path.as_posix().lower().endswith("references/providers/providers.csv"):
        return []

    errors: List[str] = []
    identities: Dict[str, tuple[str, int]] = {}

    for row_number, row in enumerate(rows, start=2):
        slug = (row.get("slug") or "").strip()
        name = (row.get("name") or "").strip()
        raw_aliases = (row.get("aliases") or "").strip()
        aliases: list[str] = []

        if raw_aliases and raw_aliases.casefold() != "null":
            try:
                parsed = json.loads(raw_aliases)
            except json.JSONDecodeError as exc:
                errors.append(f"{path}: row {row_number}: aliases must be a JSON array or NULL ({exc.msg})")
                continue
            if not isinstance(parsed, list) or any(not isinstance(alias, str) or not alias.strip() for alias in parsed):
                errors.append(f"{path}: row {row_number}: aliases must be a JSON array of non-empty strings")
                continue
            aliases = [alias.strip() for alias in parsed]

        own_identities = {identity for identity in (normalize_identity(slug), normalize_identity(name)) if identity}
        seen_aliases: set[str] = set()

        for alias in aliases:
            identity = normalize_identity(alias)
            if not identity:
                errors.append(f"{path}: row {row_number}: alias '{alias}' has no searchable characters")
                continue
            if identity in own_identities:
                errors.append(f"{path}: row {row_number}: alias '{alias}' duplicates this provider's name or slug")
            if identity in seen_aliases:
                errors.append(f"{path}: row {row_number}: alias '{alias}' duplicates another alias on the same provider")
            seen_aliases.add(identity)

        for identity in own_identities:
            previous = identities.get(identity)
            if previous and previous[0] != slug:
                errors.append(
                    f"{path}: row {row_number}: provider identity duplicates row {previous[1]} after case/punctuation normalization"
                )
            else:
                identities[identity] = (slug, row_number)

        for alias in aliases:
            identity = normalize_identity(alias)
            if not identity:
                continue
            previous = identities.get(identity)
            if previous and previous[0] != slug:
                errors.append(
                    f"{path}: row {row_number}: alias '{alias}' conflicts with provider identity on row {previous[1]}"
                )
            else:
                identities[identity] = (slug, row_number)

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
    validator.add_rule(rule_provider_aliases)
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
