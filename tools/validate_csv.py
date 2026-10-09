from pathlib import Path
from typing import Iterator, Callable, List, Dict
import os
import csv
import re
import json

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

CT_FIELDS = {"in", "name", "format"}
CT_HEADER_NAME_PATTERN = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
CT_QUERY_NAME_PATTERN = re.compile(r"^[0-9A-Za-z_.~-]+$")

def _ct_no_dup_object_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON member")
        result[key] = value
    return result

def rule_credential_transport(path: Path, rows: List[Dict[str, str]]) -> List[str]:
    if not rows or "credentialTransport" not in rows[0]:
        return []

    errors: List[str] = []

    for idx, row in enumerate(rows, start=2):  # header = row 1
        cell = (row.get("credentialTransport") or "").strip()
        if not cell or cell.lower() == "null":
            continue

        ref = f"{path}: row {idx}: credentialTransport"

        try:
            value = json.loads(cell, object_pairs_hook=_ct_no_dup_object_pairs)
        except ValueError as exc:
            message = str(exc)
            if "duplicate JSON member" in message:
                errors.append(f"{ref} has {message}")
            else:
                errors.append(f"{ref} is not valid JSON")
            continue

        if not isinstance(value, dict):
            errors.append(f"{ref} must be a JSON object")
            continue

        if not value:
            # {} explicitly clears inherited metadata; valid in any context
            continue

        if set(value) != CT_FIELDS:
            errors.append(f"{ref} must contain only in, name, format")
            continue

        hosting = (row.get("hostingType") or "").strip()
        transport = (row.get("transportType") or "").strip()
        auth = (row.get("authType") or "").strip()
        if hosting != "Hosted" or transport not in ("http", "sse") or auth == "None":
            errors.append(
                f"{ref} requires a hosted HTTP/SSE endpoint with authentication "
                f"(hostingType={hosting or 'blank'}, transportType={transport or 'blank'}, authType={auth or 'blank'})"
            )
            continue

        if value["in"] not in ("header", "query"):
            errors.append(f"{ref} has unsupported location: {value['in']!r}")
            continue

        if value["format"] not in ("raw", "bearer"):
            errors.append(f"{ref} has unsupported format: {value['format']!r}")
            continue

        name = value["name"]
        pattern = CT_HEADER_NAME_PATTERN if value["in"] == "header" else CT_QUERY_NAME_PATTERN
        if not isinstance(name, str) or not pattern.match(name):
            errors.append(f"{ref} has invalid {'header' if value['in'] == 'header' else 'query'} name")
            continue

        if value["format"] == "bearer" and (value["in"] != "header" or name.lower() != "authorization"):
            errors.append(f"{ref} bearer format requires the Authorization header")
            continue

    return errors


def main():
    root = Path(".")

    validator = CSVValidator()
    validator.add_rule(rule_slug_sorted)
    validator.add_rule(rule_credential_transport)
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
