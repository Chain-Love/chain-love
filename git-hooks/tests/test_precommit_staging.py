#!/usr/bin/env python3
"""
Regression tests for issue #3823: the pre-commit hook must not clobber a
contributor's staged CSVs and must not stage untracked ones.

Run with:

    python3 git-hooks/tests/test_precommit_staging.py

Exits non-zero on the first failing check. No third-party dependencies.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "pre-commit.py"

# The hook is named "pre-commit.py", which is not a valid module name, so it is
# loaded from source instead of imported.
_loader = importlib.machinery.SourceFileLoader("precommit_hook", str(HOOK))
_spec = importlib.util.spec_from_loader("precommit_hook", _loader)
hook = importlib.util.module_from_spec(_spec)
_loader.exec_module(hook)

FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    if ok:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}" + (f" -- {detail}" if detail else ""))
        FAILURES.append(label)


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout


def new_repo() -> Path:
    repo = Path(tempfile.mkdtemp(prefix="cl3823-"))
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    return repo


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def index_blob(repo: Path, rel: str) -> str:
    return git(repo, "show", f":{rel}")


def export_index(repo: Path) -> Path:
    """Run the hook's own index export, exactly as main() does."""
    dest = Path(tempfile.mkdtemp(prefix="cl3823-export-"))
    hook.checkout_index_tree(dest, cwd=repo)
    return dest


def scenario() -> Path:
    """The disposable repository from issue #3823."""
    repo = new_repo()
    write(repo / "data.csv", "slug,value\nalpha,original\n")
    git(repo, "add", "data.csv")
    git(repo, "commit", "-qm", "init")

    # deliberately staged edit
    write(repo / "data.csv", "slug,value\nalpha,intended\n")
    git(repo, "add", "data.csv")

    # later unstaged edit that must not leak into the commit
    write(repo / "data.csv", "slug,value\nalpha,not-ready\n")

    # unrelated untracked CSV
    write(repo / "local-notes.csv", "slug,value\nnotes,local-only-fixture\n")
    return repo


def test_untracked_csv_is_not_staged() -> None:
    print("[1] untracked CSV stays untracked")
    repo = scenario()
    try:
        export = export_index(repo)
        hook.find_unsorted_csvs(export)

        tracked = git(repo, "ls-files").split()
        check("local-notes.csv is not in the index", "local-notes.csv" not in tracked,
              f"index={tracked}")
        check("local-notes.csv is absent from the export",
              not (export / "local-notes.csv").exists())
        check("export contains only the staged CSV",
              sorted(p.name for p in export.glob("*.csv")) == ["data.csv"],
              str(sorted(p.name for p in export.glob("*.csv"))))
    finally:
        shutil.rmtree(repo, ignore_errors=True)


def test_staged_content_survives_unstaged_edit() -> None:
    print("[2] staged content is not replaced by unstaged edits")
    repo = scenario()
    try:
        export = export_index(repo)
        hook.find_unsorted_csvs(export)

        idx = index_blob(repo, "data.csv")
        check("index still holds the staged value", "intended" in idx, repr(idx))
        check("unstaged edit did not reach the index", "not-ready" not in idx, repr(idx))
        check("export shows the staged value, not the working tree",
              "intended" in (export / "data.csv").read_text(encoding="utf-8")
              and "not-ready" not in (export / "data.csv").read_text(encoding="utf-8"),
              repr((export / "data.csv").read_text(encoding="utf-8")))
        check("working tree is untouched",
              "not-ready" in (repo / "data.csv").read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(repo, ignore_errors=True)


def test_unsorted_staged_csv_is_reported_not_silently_fixed() -> None:
    print("[3] unsorted staged CSV is reported, not silently staged")
    repo = new_repo()
    try:
        write(repo / "wallets.csv", "slug,value\nzulu,1\nalpha,2\n")
        git(repo, "add", "wallets.csv")

        before_status = git(repo, "status", "--porcelain")
        before_blob = index_blob(repo, "wallets.csv")

        export = export_index(repo)
        findings = hook.find_unsorted_csvs(export)

        rel = [f[0].relative_to(export).as_posix() for f in findings]
        check("the unsorted CSV is reported", rel == ["wallets.csv"], str(rel))
        check("the offending pair is reported",
              findings and findings[0][1] == ("zulu", "alpha"), str(findings[:1]))
        check("real index left unchanged on failure",
              index_blob(repo, "wallets.csv") == before_blob)
        check("git status unchanged on failure",
              git(repo, "status", "--porcelain") == before_status)
        check("working tree left unchanged on failure",
              "zulu" in (repo / "wallets.csv").read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(repo, ignore_errors=True)


def test_sorted_csv_passes() -> None:
    print("[4] a sorted CSV produces no findings")
    repo = new_repo()
    try:
        write(repo / "wallets.csv", "slug,value\nalpha,1\nzulu,2\n")
        git(repo, "add", "wallets.csv")
        export = export_index(repo)
        check("no findings for a sorted CSV", hook.find_unsorted_csvs(export) == [])
    finally:
        shutil.rmtree(repo, ignore_errors=True)


def test_staged_deletion_is_absent_from_export() -> None:
    print("[5] a staged deletion is absent from the export")
    repo = new_repo()
    try:
        write(repo / "gone.csv", "slug,value\nalpha,1\n")
        write(repo / "kept.csv", "slug,value\nbeta,1\n")
        git(repo, "add", "gone.csv", "kept.csv")
        git(repo, "commit", "-qm", "init")

        git(repo, "rm", "-q", "gone.csv")  # staged deletion

        export = export_index(repo)
        names = sorted(p.name for p in export.glob("*.csv"))
        check("deleted file is not exported", names == ["kept.csv"], str(names))
        check("no findings for the remaining file", hook.find_unsorted_csvs(export) == [])
    finally:
        shutil.rmtree(repo, ignore_errors=True)


def test_paths_with_spaces() -> None:
    print("[6] paths containing spaces are handled")
    repo = new_repo()
    try:
        rel = "dir with space/a b.csv"
        write(repo / rel, "slug,value\nzulu,1\nalpha,2\n")
        git(repo, "add", "--", rel)

        export = export_index(repo)
        findings = hook.find_unsorted_csvs(export)
        rel_found = [f[0].relative_to(export).as_posix() for f in findings]
        check("CSV under a spaced path is found and reported",
              rel_found == [rel], str(rel_found))
    finally:
        shutil.rmtree(repo, ignore_errors=True)


def test_files_without_slug_column_are_ignored() -> None:
    print("[7] CSVs without a slug column are ignored")
    repo = new_repo()
    try:
        write(repo / "notes.csv", "title,value\nb,1\na,2\n")
        write(repo / "empty.csv", "slug,value\n")
        git(repo, "add", "notes.csv", "empty.csv")
        export = export_index(repo)
        check("no findings for files with no slug column / no rows",
              hook.find_unsorted_csvs(export) == [])
    finally:
        shutil.rmtree(repo, ignore_errors=True)


def test_hook_never_stages_anything() -> None:
    print("[8] the hook contains no staging call")
    src = HOOK.read_text(encoding="utf-8")
    stages = re.search(r'\[\s*"git"\s*,\s*[\'"]add[\'"]', src)
    check('no ["git", "add", ...] call in the hook', stages is None,
          stages.group(0) if stages else "")


def main() -> int:
    print(f"testing {HOOK}\n")
    for fn in (
        test_untracked_csv_is_not_staged,
        test_staged_content_survives_unstaged_edit,
        test_unsorted_staged_csv_is_reported_not_silently_fixed,
        test_sorted_csv_passes,
        test_staged_deletion_is_absent_from_export,
        test_paths_with_spaces,
        test_files_without_slug_column_are_ignored,
        test_hook_never_stages_anything,
    ):
        fn()
        print()

    if FAILURES:
        print(f"FAILED ({len(FAILURES)}): {', '.join(FAILURES)}")
        return 1

    print("All pre-commit staging regression checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
