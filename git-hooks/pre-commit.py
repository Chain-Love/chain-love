#!/usr/bin/env python3
from __future__ import annotations

import io
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path
from typing import Iterable
import csv

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

def detect_newline(path):
    with open(path, "rb") as f:
        chunk = f.read(8192)
    if b"\r\n" in chunk:
        return "\r\n"
    return "\n"

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

def sort_csv_by_slug(repo_root: Path) -> None:
    """
    Sort all CSV files by 'slug' column if it exists.
    Rewrites the file and stages it.
    """
    print("Sorting CSV files by slug")

    for csv_file in iter_csv(repo_root):
        with open(csv_file, newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or "slug" not in reader.fieldnames:
                continue

            rows = list(reader)
            if not rows:
                continue

        rows_sorted = sorted(rows, key=lambda r: r["slug"])
        newline_style = detect_newline(csv_file)

        with open(csv_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=reader.fieldnames, lineterminator=newline_style)
            writer.writeheader()
            writer.writerows(rows_sorted)

        subprocess.run(["git", "add", str(csv_file)], check=True)
        print(f"  sorted: {csv_file}")

def csv_quote_if_nonempty(value: str | None) -> str:
    if value is None or value == "":
        return ""
    s = str(value).replace('"', '""')
    return f'"{s}"'


def rewrite_with_quotes(repo_root: Path) -> None:
    """
    Rewrite all CSV files so that:
    - empty fields stay empty
    - non-empty fields are always double-quoted
    """
    print("Rewriting CSV files")

    for csv_file in iter_csv(repo_root):
        with open(csv_file, newline="") as f:
            reader = csv.DictReader(f)

            if not reader.fieldnames:
                continue

            rows = list(reader)
            if not rows:
                continue

        newline_style = detect_newline(csv_file)

        with open(csv_file, "w", newline="") as f:
            header = ",".join(csv_quote_if_nonempty(name) for name in reader.fieldnames)
            f.write(header + newline_style)

            for row in rows:
                line = ",".join(
                    csv_quote_if_nonempty(row.get(field))
                    for field in reader.fieldnames
                )
                f.write(line + newline_style)

        subprocess.run(["git", "add", str(csv_file)], check=True)
        print(f"  rewritten: {csv_file}")

def main() -> None:
    ensure_tool_exists("git")
    ensure_tool_exists("tar")

    # Sort CSV files
    real_root = get_repo_root()
    sort_csv_by_slug(real_root)
    rewrite_with_quotes(real_root)

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
