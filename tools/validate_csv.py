from pathlib import Path
from typing import Iterator, Callable, List, Dict
from urllib.parse import urlsplit
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

PROVIDER_URL_COLUMNS = ("website", "docs")
PROVIDER_PATH_COLUMNS = ("x", "github", "discord", "telegram", "linkedin")

def provider_link_problem(column: str, value: str) -> str:
    if "](" in value:
        return "must be a plain value, not a Markdown link"
    if column in PROVIDER_URL_COLUMNS:
        try:
            url = urlsplit(value)
            if value.startswith(("http://", "https://")) and url.hostname and not re.search(r"\s", value):
                return ""
        except ValueError:
            pass
        return "must be a full URL (lowercase http:// or https://, no spaces)"
    if re.search(r"\s", value):
        return "must not contain whitespace"
    value = value.removeprefix("@")  # the link checker strips an optional leading @
    first, _, identifier = value.partition("/")
    if ":" in value or "." in first or not first:
        return "must store only the part after the domain"
    if column == "linkedin" and not re.match(r"[^/?#]", identifier):
        return "must include a page type and identifier, such as company/example or in/example"
    return ""

def rule_provider_link_format(path: Path, rows: List[Dict[str, str]]) -> List[str]:
    # Link format of providers.csv, as in CONTRIBUTING.md, AGENTS.md and the wiki Style Guide
    if path.as_posix() != "references/providers/providers.csv":
        return []

    errors: List[str] = []

    for idx, row in enumerate(rows, start=2):  # header = row 1
        for column in PROVIDER_URL_COLUMNS + PROVIDER_PATH_COLUMNS:
            value = (row.get(column) or "").strip()
            problem = provider_link_problem(column, value) if value else ""
            if problem:
                errors.append(f"{path}: row {idx}: column '{column}': '{value}' {problem}")

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
    #validator.add_rule(rule_links_must_be_quoted)
    validator.add_rule(rule_provider_link_format)

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
