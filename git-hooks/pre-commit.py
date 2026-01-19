#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable

# ──────────────────────────────────────
# Configuration
# ──────────────────────────────────────

REMOTE = "origin"
SOURCE_BRANCH = "json-tools"
SOURCE_REF = f"{REMOTE}/{SOURCE_BRANCH}"

# Paths copied from SOURCE_REF into project root
COPY_FROM_BRANCH = [
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


def strip_depth(path: str) -> int:
    # "tools/" -> 1, "a/b/" -> 2
    return len(Path(path.rstrip("/")).parts)


def main() -> None:
    ensure_tool_exists("git")
    ensure_tool_exists("python3")

    print("Ensuring latest tools are fetched")
    run(["git", "fetch", "--quiet", REMOTE, SOURCE_BRANCH])

    with tempfile.TemporaryDirectory(prefix="precommit-root-") as tmp:
        tmp_root = Path(tmp)

        print("Creating temporary project copy")
        git_archive("HEAD", None, tmp_root)

        print(f"Overlaying tools from '{SOURCE_REF}'")
        for path in COPY_FROM_BRANCH:
            clean = path.rstrip("/")
            depth = strip_depth(path)

            # Validate path exists in source ref
            try:
                subprocess.run(
                    ["git", "show", f"{SOURCE_REF}:{clean}"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=True,
                )
            except subprocess.CalledProcessError:
                die(f"'{path}' not found in {SOURCE_REF}")

            git_archive(SOURCE_REF, path, tmp_root, strip_components=depth)

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