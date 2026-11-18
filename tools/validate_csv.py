from functools import cache
from pathlib import Path
from typing import Iterator, Callable, List, Dict
from urllib.parse import urlsplit
import os
import csv
import json
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

def rule_mcp_connection_contract(path: Path, rows: List[Dict[str, str]]) -> List[str]:
    if path.name != "mcpservers.csv" or not rows or "hostingType" not in rows[0]:
        return []
    errors: List[str] = []
    for idx, row in enumerate(rows, start=2):
        # Offer references are validated after inheritance by schema validation.
        if (row.get("offer") or "").startswith("!offer:"):
            continue
        hosting = (row.get("hostingType") or "").strip()
        transport = (row.get("transportType") or "").strip()
        endpoint = (row.get("mcpEndpoint") or "").strip()
        command = (row.get("selfHostedCommand") or "").strip()
        raw_args = (row.get("selfHostedArgs") or "").strip()
        if hosting == "Hosted" and transport in {"http", "sse"}:
            if not looks_like_url(endpoint):
                errors.append(f"{path}: row {idx}: Hosted {transport} MCP server requires an http(s) mcpEndpoint")
        if hosting == "Self-hosted":
            if not command:
                errors.append(f"{path}: row {idx}: Self-hosted MCP server requires selfHostedCommand")
            if not raw_args:
                errors.append(f"{path}: row {idx}: Self-hosted MCP server requires selfHostedArgs (use [] for a bare command)")
            else:
                try:
                    args = json.loads(raw_args)
                except json.JSONDecodeError as exc:
                    errors.append(f"{path}: row {idx}: selfHostedArgs is not valid JSON: {exc.msg}")
                else:
                    if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
                        errors.append(f"{path}: row {idx}: selfHostedArgs must be a JSON array of strings")
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
    validator.add_rule(rule_mcp_connection_contract)
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
