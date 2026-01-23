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

# ──────────────────────────────────────
# Configuration
# ──────────────────────────────────────

UPSTREAM_REPO = "Chain-Love/chain-love"
UPSTREAM_REF = "json-tools"
UPSTREAM_URL = f"https://github.com/{UPSTREAM_REPO}/archive/{UPSTREAM_REF}.tar.gz"

# Paths copied from upstream repo into project root
COPY_FROM_UPSTREAM = [
    "tools/",
]

# Scripts expected to end up in project root
SCRIPTS = [
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


def git_archive(ref: str, path: str | None, dest: Path, strip_components: int = 0) -> None:
    """
    Archive `path` (or whole tree if None) from `ref` into `dest`,
    stripping `strip_components` leading path elements.
    """
    archive_cmd = ["git", "archive", ref]
    if path:
        archive_cmd.append(path)

    extract_cmd = [
        "tar",
        "-x",
        "-C",
        str(dest),
    ]
    if strip_components:
        extract_cmd.append(f"--strip-components={strip_components}")

    archive = subprocess.Popen(archive_cmd, stdout=subprocess.PIPE)
    try:
        subprocess.run(
            extract_cmd,
            stdin=archive.stdout,
            check=True,
        )
    finally:
        archive.stdout and archive.stdout.close()
        archive.wait()


def ensure_tool_exists(name: str) -> None:
    if shutil.which(name) is None:
        die(f"{name} not found in PATH")

def download_and_extract(url: str, dest: Path, subpath: str) -> None:
    """
    Download a GitHub tarball and extract only `subpath`
    into `dest`, stripping the repo root prefix.
    """
    print(f"- downloading {url} ({subpath})")

    with urllib.request.urlopen(url) as resp:
        data = resp.read()

    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        members = tar.getmembers()
        if not members:
            die("Downloaded archive is empty")

        root = members[0].name.split("/")[0]
        prefix = f"{root}/{subpath.rstrip('/')}/"

        selected = [
            m for m in members
            if m.name.startswith(prefix)
        ]

        if not selected:
            die(f"Path '{subpath}' not found in upstream archive")

        for m in selected:
            m.name = m.name[len(prefix):]  # strip leading dirs
            if m.name:
                tar.extract(m, dest)


def main() -> None:
    ensure_tool_exists("git")

    with tempfile.TemporaryDirectory(prefix="precommit-root-") as tmp:
        tmp_root = Path(tmp)

        print("Creating temporary project copy")
        git_archive("HEAD", None, tmp_root)

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
