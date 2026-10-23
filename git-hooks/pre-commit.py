#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path
from typing import Iterable

# ──────────────────────────────────────
# Configuration
# ──────────────────────────────────────

UPSTREAM_REPO = "Chain-Love/chain-love"
UPSTREAM_REF = "json-tools"
UPSTREAM_URL = f"https://github.com/{UPSTREAM_REPO}/archive/{UPSTREAM_REF}.tar.gz"

# Paths copied from upstream repo into project root
COPY_FROM_UPSTREAM = [
    "tools/*",
    "meta",
]

# Scripts expected to end up in project root
SCRIPTS = [
    "validate_csv.py",
    "csv_to_json.py",
    "validate.py",
]

# ──────────────────────────────────────
# Helpers
# ──────────────────────────────────────

def die(msg: str) -> None:
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


def run(cmd: Iterable[str], *, cwd: Path | None = None) -> None:
    print("-", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)

def checkout_index_tree(dest: Path) -> None:
    """
    Populate dest with the complete Git index tree
    (exactly what the repo will look like after commit).
    """
    print("Checking out full index tree")

    run(
        [
            "git",
            "checkout-index",
            "-a",        # all files
            "-f",        # overwrite
            f"--prefix={dest}/",
        ]
    )

def ensure_tool_exists(name: str) -> None:
    if shutil.which(name) is None:
        die(f"{name} not found in PATH")

def download_and_extract(url: str, dest: Path, subpath: str) -> None:
    """
    Download a GitHub tarball and extract only `subpath`
    into `dest`, stripping the repo root prefix.
    """
    print(f"- downloading {url} ({subpath})")

    flatten = subpath.endswith("/*")
    subpath = subpath.rstrip("/*").rstrip("/")

    with urllib.request.urlopen(url) as resp:
        data = resp.read()

    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        members = tar.getmembers()
        if not members:
            die("Downloaded archive is empty")

        root = members[0].name.split("/")[0]
        full_prefix = f"{root}/{subpath}/"

        selected = [
            m for m in members
            if m.name.startswith(full_prefix)
        ]

        if not selected:
            die(f"Path '{subpath}' not found in upstream archive")

        for m in selected:
            if flatten:
                # strip root/subpath/
                strip_prefix = full_prefix
            else:
                # strip only root/
                strip_prefix = f"{root}/"

            relative_name = m.name[len(strip_prefix):]
            if not relative_name:
                continue

            target_path = dest / relative_name
            target_path.parent.mkdir(parents=True, exist_ok=True)

            if m.isdir():
                target_path.mkdir(parents=True, exist_ok=True)
            else:
                with tar.extractfile(m) as src, open(target_path, "wb") as out:
                    shutil.copyfileobj(src, out)

def split_record_ending(record: str) -> tuple[str, str]:
    """Separate a CSV record's terminator, leaving embedded newlines intact."""
    for ending in ("\r\n", "\n", "\r"):
        if record.endswith(ending):
            return record[:-len(ending)], ending
    return record, ""

def get_repo_root() -> Path:
    out = subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"],
        text=True,
    ).strip()
    return Path(out)

def iter_csv(repo_root: Path) -> Iterable[Path]:
    for csv_file in repo_root.rglob("*.csv"):
        if ".git" in csv_file.parts:
            continue
        yield csv_file

def sort_csv_by_slug(repo_root: Path, delimiter: str = ",") -> None:
    """
    Sort complete CSV records by slug without rewriting their fields.
    """
    print("Sorting CSV files by slug")

    for csv_file in iter_csv(repo_root):
        with csv_file.open("r", newline="") as f:
            lines = f.readlines()

        if len(lines) <= 1:
            continue

        reader = csv.reader(lines, delimiter=delimiter, strict=True)
        header_parts = [cell.strip() for cell in next(reader)]

        if "slug" not in header_parts:
            continue

        slug_idx = header_parts.index("slug")
        header = "".join(lines[:reader.line_num])
        _, newline_style = split_record_ending(header)
        start = reader.line_num
        records = []
        for row in reader:
            # line_num counts physical lines consumed by each logical record.
            # Retain those source lines so quoting and field data stay exact.
            raw_record = "".join(lines[start:reader.line_num])
            start = reader.line_num
            body, ending = split_record_ending(raw_record)
            slug = row[slug_idx].strip() if slug_idx < len(row) else ""
            records.append((slug, body, ending))

        if not records:
            continue

        trailing_newline = bool(records[-1][2])
        rows_sorted = sorted(records, key=lambda record: record[0])

        with csv_file.open("w", newline="") as f:
            f.write(header)
            previous_ended_with_cr = header.endswith("\r")
            for index, (_, body, ending) in enumerate(rows_sorted):
                if index < len(rows_sorted) - 1 or trailing_newline:
                    # A formerly final record may need a separator after moving.
                    ending = ending or newline_style
                else:
                    ending = ""
                record = body + ending
                if previous_ended_with_cr and record.startswith("\n"):
                    # Keep a CR record boundary and a following empty LF record
                    # separate: otherwise they would merge into a single CRLF.
                    f.write("\n")
                f.write(record)
                previous_ended_with_cr = record.endswith("\r")

        subprocess.run(["git", "add", str(csv_file)], check=True)
        print(f"  sorted: {csv_file}")


def main() -> None:
    ensure_tool_exists("git")
    ensure_tool_exists("tar")

    # Sort CSV files
    real_root = get_repo_root()
    sort_csv_by_slug(real_root)

    with tempfile.TemporaryDirectory(prefix="precommit-root-") as tmp:
        tmp_root = Path(tmp)

        print("Creating workspace from post-commit state")
        checkout_index_tree(tmp_root)

        print(f"Overlaying tools from GitHub ({UPSTREAM_REPO}@{UPSTREAM_REF})")
        for path in COPY_FROM_UPSTREAM:
            download_and_extract(UPSTREAM_URL, tmp_root, path)

        python = sys.executable

        requirements = tmp_root / "requirements.txt"
        if requirements.exists():
            print("Installing dependencies")
            venv_dir = tmp_root / ".venv"
            run([python, "-m", "venv", str(venv_dir)])

            if sys.platform == "win32":
                venv_python = venv_dir / "Scripts" / "python.exe"
            else:
                venv_python = venv_dir / "bin" / "python"
            python = str(venv_python)

            run([
                python,
                "-m",
                "pip",
                "install",
                "--quiet",
                "--disable-pip-version-check",
                "-r",
                str(requirements),
            ])

        print("Running scripts in project root context")
        for script in SCRIPTS:
            script_path = tmp_root / script
            if not script_path.exists():
                die(f"Script not found: {script}")

            run([python, script], cwd=tmp_root)

        print("Pre-commit checks passed")


if __name__ == "__main__":
    main()
