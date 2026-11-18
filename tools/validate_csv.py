from functools import cache
from pathlib import Path
from typing import Iterator, Callable, List, Dict
from urllib.parse import urlsplit
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

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.json"

@cache
def boolean_columns() -> Dict[str, List[str]]:
    """Maps a CSV file name (wallets, faucets, ...) to its boolean columns in schema.json."""
    with SCHEMA_PATH.open(encoding="utf-8") as f:
        defs = json.load(f)["$defs"]

    columns: Dict[str, List[str]] = {}
    for name, definition in defs.items():
        columns[name] = []
        for column, spec in definition.get("properties", {}).items():
            types = spec.get("type")
            if "boolean" in (types if isinstance(types, list) else [types]):
                columns[name].append(column)

    columns["providers"] = columns.get("providerMeta", [])  # rows of providers.csv
    return columns

def rule_boolean_values(path: Path, rows: List[Dict[str, str]]) -> List[str]:
    parts = path.parts
    is_category_csv = (
        parts[:-1] in (("references", "offers"), ("listings", "all-networks"))
        or (len(parts) == 4 and parts[:2] == ("listings", "specific-networks"))
    )
    if path != Path("references/providers/providers.csv") and not is_category_csv:
        return []

    columns = boolean_columns().get(path.stem, [])
    errors: List[str] = []

    for idx, row in enumerate(rows, start=2):  # header = row 1
        for column in columns:
            value = row.get(column)
            if value and value not in ("TRUE", "FALSE"):  # a blank listing cell inherits from the offer
                errors.append(
                    f"{path}: row {idx}: column '{column}': boolean value must be TRUE or FALSE (uppercase), got '{value}'"
                )

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

BRIDGE_SUPPORTED_CHAIN_ALIASES = {
    "arbitrum one": "arbitrum",
    "bnb chain": "bsc",
    "bnb smart chain": "bsc",
    "ethereum mainnet": "ethereum",
    "klaytn": "kaia",
    "manta pacific": "manta",
    "manta pacific mainnet": "manta",
    "plume mainnet": "plume",
    "rari network": "rari",
    "saga evm": "saga-evm",
    "sui mainnet": "sui",
    "world chain": "world-chain",
    "x layer": "x-layer",
    "xrpl evm": "xrpl-evm",
    "zksync era": "zksync",
}

def rule_bridge_supported_chains(path: Path, rows: List[Dict[str, str]]) -> List[str]:
    if path.name != "bridges.csv" or not rows or "supportedChains" not in rows[0]:
        return []
    errors: List[str] = []
    for idx, row in enumerate(rows, start=2):
        raw = (row.get("supportedChains") or "").strip()
        if not raw or raw.startswith("!offer:"):
            continue
        try:
            values = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"{path}: row {idx}: supportedChains is not valid JSON: {exc.msg}")
            continue
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            errors.append(f"{path}: row {idx}: supportedChains must be a JSON array of strings")
            continue
        for value in values:
            canonical = BRIDGE_SUPPORTED_CHAIN_ALIASES.get(value)
            if canonical:
                errors.append(f"{path}: row {idx}: supportedChains uses alias {value!r}; use repository network id {canonical!r}")
        if len(values) != len(set(values)):
            errors.append(f"{path}: row {idx}: supportedChains contains duplicate network ids")
    return errors

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
    validator.add_rule(rule_boolean_values)
    validator.add_rule(rule_slug_sorted)
    validator.add_rule(rule_bridge_supported_chains)
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
