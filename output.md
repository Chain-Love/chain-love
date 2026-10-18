## Parallel execution results

### Subtask 1/1
#!/usr/bin/env python3
"""
CSV Invite‑Prefix Checker

This script scans a CSV file for rows where the ``telegram`` column starts
with a ``+`` character, which can trigger CSV‑injection attacks in
spreadsheet applications.  It logs the findings and exits with a
non‑zero status if any such rows are detected.

The implementation follows production‑grade best practices:
* Robust error handling with specific exception types
* Full type annotations
* Structured logging with configurable levels
* Input validation and security checks
* Performance‑friendly streaming where possible
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
from pathlib import Path
from typing import Iterable, List, Tuple, Dict, Any, Optional

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

DEFAULT_LOG_LEVEL: int = logging.INFO
DEFAULT_CSV_PATH: str = "references/providers/providers.csv"
REQUIRED_COLUMNS: frozenset[str] = frozenset({"slug", "telegram"})
MAX_EXAMPLE_COUNT: int = 3

# --------------------------------------------------------------------------- #
# Logging configuration
# --------------------------------------------------------------------------- #

def configure_logging(level: int | None = None) -> None:
    """
    Configure the root logger.

    Parameters
    ----------
    level : int | None
        Logging level. If ``None`` the level is taken from the
        ``AIGON_X_LOG_LEVEL`` environment variable or falls back to
        :data:`DEFAULT_LOG_LEVEL`.
    """
    if level is None:
        env = os.getenv("AIGON_X_LOG_LEVEL")
        level = int(env) if env and env.isdigit() else DEFAULT_LOG_LEVEL

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

# --------------------------------------------------------------------------- #
# Argument parsing
# --------------------------------------------------------------------------- #

def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    """
    Parse command‑line arguments.

    Parameters
    ----------
    argv : List[str] | None
        Argument list. If ``None`` ``sys.argv[1:]`` is used.

    Returns
    -------
    argparse.Namespace
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Detect plus‑prefixed Telegram invites in a CSV."
    )
    parser.add_argument(
        "csv_file",
        nargs="?",
        default=DEFAULT_CSV_PATH,
        help="Path to the CSV file to scan.",
    )
    parser.add_argument(
        "--log-level",
        type=int,
        choices=[logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL],
        help="Override the default log level.",
    )
    return parser.parse_args(argv)

# --------------------------------------------------------------------------- #
# CSV validation
# --------------------------------------------------------------------------- #

def validate_csv_file(csv_path: Path) -> None:
    """
    Validate that the CSV file exists, is readable, and contains the
    required columns.

    Parameters
    ----------
    csv_path : Path
        Path to the CSV file.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    PermissionError
        If the file cannot be read.
    ValueError
        If required columns are missing.
    """
    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    try:
        with csv_path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            header = next(reader)
    except PermissionError as exc:
        raise PermissionError(f"Permission denied while reading {csv_path}") from exc
    except Exception as exc:  # pragma: no cover
        raise PermissionError(f"Unable to read CSV header: {exc}") from exc

    missing = REQUIRED_COLUMNS - set(header)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

# --------------------------------------------------------------------------- #
# CSV scanning
# --------------------------------------------------------------------------- #

def scan_csv(csv_path: Path) -> Tuple[int, List[Tuple[str, str]]]:
    """
    Scan the CSV file for rows where the ``telegram`` field starts with '+'.

    Parameters
    ----------
    csv_path : Path
        Path to the CSV file.

    Returns
    -------
    Tuple[int, List[Tuple[str, str]]]
        Total number of rows processed and a list of offending rows
        represented as ``(slug, telegram)`` tuples.
    """
    total_rows: int = 0
    matches: List[Tuple[str, str]] = []

    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader: csv.DictReader = csv.DictReader(f)
        for row in reader:
            total_rows += 1
            telegram: str = row.get("telegram", "")
            if telegram.startswith("+"):
                matches.append((row.get("slug", ""), telegram))

    return total_rows, matches

# --------------------------------------------------------------------------- #
# Main entry point
# --------------------------------------------------------------------------- #

def main(argv: List[str] | None = None) -> int:
    """
    Main entry point.

    Parameters
    ----------
    argv : List[str] | None
        Optional list of command‑line arguments. If ``None`` ``sys.argv[1:]`` is used.

    Returns
    -------
    int
        Exit code: 0 if no plus‑prefixed telegrams found, 1 otherwise.
    """
    args = parse_args(argv)
    configure_logging(args.log_level)

    csv_path = Path(args.csv_file).expanduser().resolve()
    logging.debug("Using CSV file: %s", csv_path)

    try:
        validate_csv_file(csv_path)
    except (FileNotFoundError, PermissionError, ValueError) as exc:
        logging.error("CSV validation failed: %s", exc)
        return 1

    try:
        total_rows, matches = scan_csv(csv_path)
    except Exception as exc:  # pragma: no cover
        logging.exception("Unexpected error while scanning CSV")
        return 1

    logging.info("providers %d plus_invites %d", total_rows, len(matches))
    if matches:
        examples = matches[:MAX_EXAMPLE_COUNT]
        logging.warning("Examples: %s", examples)
        return 1

    logging.info("No plus‑prefixed telegram invites found.")
    return 0

if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))


