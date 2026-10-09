from pathlib import Path
from typing import Iterator, Callable, List, Dict
import os
import csv
import json
import re
from urllib.parse import unquote

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

NPM_NAME_PATTERN = re.compile(r"^(?:@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*$")
NPM_VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
NPM_SOURCE_PATTERN = re.compile(r"^https://registry\.npmjs\.org/[^?#]+/[^/?#]+$")
PEER_FIELDS = {"package", "version", "source", "requirements"}
PEER_REQUIREMENT_FIELDS = {"constraint", "optional"}


def _no_dup_object_pairs(pairs):
    seen = set()
    for key, _value in pairs:
        if key in seen:
            raise ValueError(f"duplicate JSON member '{key}'")
        seen.add(key)
    return dict(pairs)


def _npm_source_matches(source: str, package: str, version: str) -> bool:
    prefix = "https://registry.npmjs.org/"
    rest = source[len(prefix):]
    if not rest or "?" in rest or "#" in rest:
        return False
    parts = rest.split("/")
    if len(parts) < 2:
        return False
    src_version = parts[-1]
    src_package = "/".join(parts[:-1])
    if version == "latest" or src_version == "latest":
        return False
    if src_version != version:
        return False
    if unquote(src_package) != package:
        return False
    return True


def rule_peer_requirements(path: Path, rows: List[Dict[str, str]]) -> List[str]:
    if not rows or "peerRequirements" not in rows[0]:
        return []

    errors: List[str] = []

    for idx, row in enumerate(rows, start=2):  # header = row 1
        cell = (row.get("peerRequirements") or "").strip()
        if not cell:
            continue

        ref = f"{path}: row {idx}: peerRequirements"

        try:
            data = json.loads(cell, object_pairs_hook=_no_dup_object_pairs)
        except ValueError as exc:
            message = str(exc)
            if "duplicate JSON member" in message:
                errors.append(f"{ref} has {message}")
            else:
                errors.append(f"{ref} is not valid JSON")
            continue

        if not isinstance(data, dict):
            errors.append(
                f"{ref} must be a non-empty JSON object (missing info must stay blank, not {{}}"
                f" and not a list/scalar)"
            )
            continue

        if not data:
            errors.append(
                f"{ref} must be a non-empty JSON object (missing info must stay blank, not {{}})"
            )
            continue

        missing = PEER_FIELDS - set(data)
        extra = set(data) - PEER_FIELDS
        if missing:
            errors.append(
                f"{ref} record is missing required field(s): {', '.join(sorted(missing))}"
            )
        if extra:
            errors.append(
                f"{ref} record has unknown field(s): {', '.join(sorted(extra))}"
            )
        if missing or extra:
            continue

        package = data.get("package")
        version = data.get("version")
        source = data.get("source")
        requirements = data.get("requirements")

        shape_ok = True

        if not isinstance(package, str) or not NPM_NAME_PATTERN.match(package):
            errors.append(
                f"{ref}: package must be a lowercase npm package name "
                f"(optional @scope/ prefix), got {package!r}"
            )
            shape_ok = False

        if not isinstance(version, str) or not NPM_VERSION_PATTERN.match(version):
            errors.append(
                f"{ref}: version must be a concrete x.y.z release "
                f"(mutable tags like 'latest' are rejected), got {version!r}"
            )
            shape_ok = False

        if not isinstance(source, str) or not NPM_SOURCE_PATTERN.match(source):
            errors.append(
                f"{ref}: source must be a version-pinned "
                f"https://registry.npmjs.org/<package>/<version> URL without "
                f"query/fragment, got {source!r}"
            )
            shape_ok = False

        if not isinstance(requirements, dict) or not requirements:
            errors.append(
                f"{ref}: requirements must be a non-empty object mapping package "
                f"names to {{constraint, optional}}"
            )
            shape_ok = False
        else:
            for req_name, req in requirements.items():
                if not isinstance(req_name, str) or not NPM_NAME_PATTERN.match(req_name):
                    errors.append(
                        f"{ref}: requirements key {req_name!r} must be a lowercase "
                        f"npm package name (optional @scope/ prefix)"
                    )
                    shape_ok = False
                    continue
                if not isinstance(req, dict) or set(req) != PEER_REQUIREMENT_FIELDS:
                    got = sorted(req) if isinstance(req, dict) else type(req).__name__
                    errors.append(
                        f"{ref}: requirements[{req_name!r}] must be exactly "
                        f"{{constraint, optional}}, got {got}"
                    )
                    shape_ok = False
                    continue
                constraint = req.get("constraint")
                if not isinstance(constraint, str) or not re.search(r"\S", constraint):
                    errors.append(
                        f"{ref}: requirements[{req_name!r}].constraint must be a "
                        f"non-empty string preserving the upstream expression, "
                        f"got {constraint!r}"
                    )
                    shape_ok = False
                if not isinstance(req.get("optional"), bool):
                    errors.append(
                        f"{ref}: requirements[{req_name!r}].optional must be the "
                        f"JSON boolean true/false (peerDependenciesMeta flag), "
                        f"got {req.get('optional')!r}"
                    )
                    shape_ok = False

        if shape_ok and not _npm_source_matches(source, package, version):
            errors.append(
                f"{ref}: source {source!r} does not match declared "
                f"package {package!r} version {version!r}"
            )

    return errors


def main():
    root = Path(".")

    validator = CSVValidator()
    validator.add_rule(rule_slug_sorted)
    validator.add_rule(rule_peer_requirements)
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
