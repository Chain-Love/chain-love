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


# DBIP #1943: chain vs slug consistency in specific-network listings.
# Known chain tokens and the family (testnet/mainnet) they belong to.
CHAIN_FAMILY = {
    "mainnet": "mainnet",
    "sepolia": "testnet",
    "hoodi": "testnet",
    "calibnet": "testnet",
    "testnet": "testnet",
    "devnet": "testnet",
    "coston2": "testnet",
    "amoy": "testnet",
}
CHAIN_NON_SIGNAL = {"one", "nova"}


def _load_chain_allowlist() -> set:
    """Load (path, slug) pairs for explicit cross-network chain values."""
    p = Path("tools/chain_allowlist.csv")
    if not p.exists():
        return set()
    allow = set()
    try:
        with p.open(newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                allow.add((r.get("path", ""), r.get("slug", "")))
    except Exception:
        pass
    return allow


def rule_chain_slug_consistency(path: Path, rows: List[Dict[str, str]]) -> List[str]:
    """DBIP #1943: reject chain values that contradict slug network signals.

    For listings under listings/specific-networks/, compares each row's chain
    value against network tokens embedded in the slug (mainnet, sepolia, hoodi,
    calibnet, testnet, devnet, coston2, amoy). If the slug declares one family
    (mainnet vs testnet) and the chain declares the opposite, the row is an
    error unless explicitly allowlisted in tools/chain_allowlist.csv.
    """
    errors: List[str] = []
    if not str(path).startswith("listings/specific-networks/"):
        return errors
    if not rows or "slug" not in rows[0] or "chain" not in rows[0]:
        return errors
    allow = _load_chain_allowlist()
    for idx, row in enumerate(rows, start=2):
        slug = (row.get("slug") or "").strip()
        chain = (row.get("chain") or "").strip()
        if not slug or not chain:
            continue
        if (str(path), slug) in allow:
            continue
        slug_fams = {CHAIN_FAMILY[t] for t in slug.split("-") if t in CHAIN_FAMILY and t not in CHAIN_NON_SIGNAL}
        chain_fams = {CHAIN_FAMILY[t] for t in chain.split("-") if t in CHAIN_FAMILY and t not in CHAIN_NON_SIGNAL}
        if slug_fams and chain_fams and not (slug_fams & chain_fams):
            errors.append(
                f"{path}: row {idx}: slug '{slug}' declares {sorted(slug_fams)} but chain='{chain}' "
                f"({sorted(chain_fams)}); fix chain or allowlist it in tools/chain_allowlist.csv"
            )
    return errors


def main():
    root = Path(".")

    validator = CSVValidator()
    validator.add_rule(rule_slug_sorted)
    validator.add_rule(rule_chain_slug_consistency)
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
