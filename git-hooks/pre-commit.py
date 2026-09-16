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

def checkout_index_tree(dest: Path, *, cwd: Path) -> None:
    """
    Populate dest with the complete Git index tree
    (exactly what the repo will look like after commit).

    This export is the only view of the repository the hook is allowed to
    read. The real working tree and the real index are never written to, so a
    contributor's deliberately staged content is never replaced with later
    unstaged edits, and untracked files are never pulled into the commit
    (issue #3823).
    """
    print("Checking out full index tree")

    run(
        [
            "git",
            "checkout-index",
            "-a",        # all files
            "-f",        # overwrite
            f"--prefix={dest.as_posix()}/",
        ],
        cwd=cwd,
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

def get_repo_root() -> Path:
    out = subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"],
        text=True,
    ).strip()
    return Path(out)

def iter_csv(root: Path) -> Iterable[Path]:
    """
    Yield every CSV under `root`.

    `root` must be an isolated index export, never the real working tree:
    walking the working tree would also pick up untracked CSVs, which is how
    unrelated files used to end up in the commit (issue #3823).
    """
    for csv_file in root.rglob("*.csv"):
        if ".git" in csv_file.parts:
            continue
        yield csv_file

def read_slug_column(csv_file: Path, delimiter: str = ",") -> list[str] | None:
    """
    Return the slug column of `csv_file` in file order, or None when the file
    has no slug column or no data rows (nothing to order).
    """
    with csv_file.open("r", newline="") as f:
        lines = f.readlines()

    if len(lines) <= 1:
        return None

    header_parts = [h.strip().strip('"') for h in lines[0].rstrip("\r\n").split(delimiter)]

    if "slug" not in header_parts:
        return None

    slug_idx = header_parts.index("slug")
    slugs: list[str] = []

    for raw_line in lines[1:]:
        if not raw_line.strip():
            continue

        parts = raw_line.rstrip("\r\n").split(delimiter)

        cell = "" if slug_idx >= len(parts) else parts[slug_idx].strip()

        # normalize quoted slug for comparison
        if len(cell) >= 2 and cell.startswith('"') and cell.endswith('"'):
            cell = cell[1:-1]

        slugs.append(cell)

    return slugs

def find_unsorted_csvs(
    root: Path,
    delimiter: str = ",",
) -> list[tuple[Path, tuple[str, str]]]:
    """
    Report CSVs whose slug column is not in ascending order.

    Returns [(path, (earlier_slug, later_slug))] for the first out-of-order
    pair of each file. This is a check only: nothing is written and nothing is
    staged, so a failure leaves the real index and working tree untouched
    (issue #3823).
    """
    print("Checking CSV slug ordering")

    findings: list[tuple[Path, tuple[str, str]]] = []

    for csv_file in sorted(iter_csv(root)):
        slugs = read_slug_column(csv_file, delimiter)
        if not slugs:
            continue

        for earlier, later in zip(slugs, slugs[1:]):
            if earlier > later:
                findings.append((csv_file, (earlier, later)))
                break

    return findings

def looks_like_url(v: str) -> bool:
    return v.startswith("http://") or v.startswith("https://")


def main() -> None:
    ensure_tool_exists("git")
    ensure_tool_exists("tar")

    # The real repository is used only to locate the root and to export the
    # index. Nothing here writes to the working tree or to the real index.
    real_root = get_repo_root()

    with tempfile.TemporaryDirectory(prefix="precommit-root-") as tmp:
        tmp_root = Path(tmp)

        print("Creating workspace from post-commit state")
        checkout_index_tree(tmp_root, cwd=real_root)

        # Ordering is checked on the isolated index export, so an unsorted CSV
        # is reported instead of being silently re-sorted and restaged: doing
        # that would also stage any unstaged edits in the same file.
        unsorted = find_unsorted_csvs(tmp_root)
        if unsorted:
            lines = [f"{len(unsorted)} staged CSV file(s) are not sorted by slug:"]
            for csv_file, (earlier, later) in unsorted:
                rel = csv_file.relative_to(tmp_root).as_posix()
                lines.append(f"  - {rel}: {earlier!r} appears before {later!r}")
            lines.append("")
            lines.append("The hook no longer sorts these for you: rewriting and staging")
            lines.append("them here would also stage any unstaged edits in the same file.")
            lines.append("Sort each file by its slug column, keeping the header first,")
            lines.append("then stage the result deliberately:")
            lines.append("")
            lines.append("    git add <file>")
            die("\n".join(lines))

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
