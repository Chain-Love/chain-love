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


AUTH_PERMISSION_COLUMN = "authPermissionRequirements"
_AUTH_PERM_FIELDS = {"authMethod", "operation", "permissions", "sourceUrl"}
_SCOPE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_CRED_RE = re.compile(
    r"^(gh[pousr]_|github_pat_|ghs_|gho_|ghu_|glpat-|xox[bpars]-|hf_|sk-|pat_|AKIA[0-9A-Z]{16}|Bearer\s|eyJ[A-Za-z0-9_-]{10,})",
    re.IGNORECASE,
)
_URL_USERINFO_RE = re.compile(r"^https://[^/@\s]+:[^/@\s]+@")
_TOKEN_QS_RE = re.compile(r"[?&](token|key|secret|password|api_key|access_token)=", re.IGNORECASE)


def rule_auth_permission_requirements(path: Path, rows: List[Dict[str, str]]) -> List[str]:
    """authPermissionRequirements must be a non-empty JSON array of four-field
    records with exact fields, non-empty scope-shaped permission strings that are
    never credential values, and a well-formed public https sourceUrl.
    Missing/unknown information stays blank (null) - blank cells are skipped."""
    if not rows or AUTH_PERMISSION_COLUMN not in rows[0]:
        return []

    errors: List[str] = []

    for idx, row in enumerate(rows, start=2):  # header = row 1
        cell = (row.get(AUTH_PERMISSION_COLUMN) or "").strip()
        if not cell:
            continue
        where = f"{path}: row {idx}"

        try:
            val = json.loads(cell)
        except Exception:
            errors.append(f"{where}: {AUTH_PERMISSION_COLUMN} is not valid JSON")
            continue
        if not isinstance(val, list) or not val:
            errors.append(f"{where}: {AUTH_PERMISSION_COLUMN} must be a non-empty JSON array (missing info must stay blank, not [])")
            continue

        seen_records = set()
        for rnum, rec in enumerate(val):
            rwhere = f"{where}: record {rnum}"
            if not isinstance(rec, dict):
                errors.append(f"{rwhere}: record must be a JSON object")
                continue
            if set(rec) != _AUTH_PERM_FIELDS:
                errors.append(f"{rwhere}: fields must be exactly authMethod, operation, permissions, sourceUrl (got {sorted(rec)})")
                continue

            for field in ("authMethod", "operation"):
                v = rec[field]
                if not isinstance(v, str) or not v.strip():
                    errors.append(f"{rwhere}: {field} must be a non-empty string")
            if not isinstance(rec.get("authMethod"), str) or not isinstance(rec.get("operation"), str):
                continue

            perms = rec["permissions"]
            if not isinstance(perms, list) or not perms:
                errors.append(f"{rwhere}: permissions must be a non-empty array")
                continue
            perm_bad = False
            for perm in perms:
                if not isinstance(perm, str) or not _SCOPE_RE.match(perm):
                    errors.append(f"{rwhere}: permission {perm!r} must be a scope-shaped non-empty string")
                    perm_bad = True
                elif _CRED_RE.match(perm):
                    errors.append(f"{rwhere}: permission {perm!r} looks like a credential/token value - document permissions only, never secrets")
                    perm_bad = True
            if perm_bad:
                continue

            url = rec["sourceUrl"]
            if not isinstance(url, str) or not url.startswith("https://") or " " in url or _URL_USERINFO_RE.match(url) or _TOKEN_QS_RE.search(url):
                errors.append(f"{rwhere}: sourceUrl must be a well-formed public https:// URL without credentials or token query parameters")
                continue

            key = json.dumps(rec, sort_keys=True)
            if key in seen_records:
                errors.append(f"{rwhere}: duplicate record")
            seen_records.add(key)

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
    validator.add_rule(rule_auth_permission_requirements)
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
