"""Regression tests for validate_key_export_formats (DBIP #3725).

One case per documented rule, plus the wiring assertion that makes the negative
controls in CI meaningful: the unit cases call the function directly, so they
cannot notice the call being removed from main().

Run: python3 tools/tests/test_key_export_formats.py
"""
from __future__ import annotations

import inspect as _inspect
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import csv_to_json as tool  # noqa: E402

CONTEXT = "network 'demo'"
FAILURES: list[str] = []
CHECKS = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if condition:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}{(' :: ' + detail) if detail else ''}")
        FAILURES.append(label)


def run(value, *, present: bool = True, slug: str = "demo-wallet", context: str = CONTEXT):
    """Call the validator with one wallets row and return the error list."""
    item = {"slug": slug} if present else {}
    if present:
        item["keyExportFormats"] = value
    return tool.validate_key_export_formats([item], context=context)


def errors_for(value, **kw) -> list[str]:
    return run(value, **kw)


def expect_ok(label: str, value, *, present: bool = True) -> None:
    errs = run(value, present=present)
    check(label, errs == [], f"expected no errors, got {errs}")


def expect_error(label: str, value, needle: str) -> None:
    errs = run(value)
    joined = "\n".join(errs)
    check(
        label,
        len(errs) >= 1 and needle in joined and not any(needle not in e for e in errs),
        f"expected every error to contain {needle!r}, got {errs}",
    )


def main() -> int:
    print("validate_key_export_formats - rule coverage")

    print("\n[accepted]")
    expect_ok("blank cell (key absent) is accepted", None, present=False)
    expect_ok("explicit null is accepted", None)
    expect_ok("empty array is accepted (explicit: none documented)", [])
    expect_ok("single valid name is accepted", ["mnemonic"])
    expect_ok("two valid names, sorted, are accepted", ["encrypted-backup", "mnemonic"])
    expect_ok(
        "all three valid names, sorted, are accepted",
        ["encrypted-backup", "mnemonic", "raw-private-key"],
    )

    print("\n[rejected: enum]")
    expect_error("unknown name is rejected", ["seed-phrase"], "must be one of")
    expect_error("near-miss name is rejected", ["mnemonics"], "must be one of")
    expect_error("empty string entry is rejected", [""], "must be one of")
    expect_error("non-string entry is rejected", [7], "must be one of")

    print("\n[rejected: uniqueness]")
    expect_error("duplicate entry is rejected", ["mnemonic", "mnemonic"], "duplicates format")
    expect_error(
        "duplicate is rejected even in a longer array",
        ["encrypted-backup", "mnemonic", "mnemonic"],
        "duplicates format",
    )

    print("\n[rejected: order]")
    expect_error(
        "unsorted array is rejected",
        ["mnemonic", "encrypted-backup"],
        "must be sorted alphabetically",
    )
    expect_error(
        "reverse-sorted array is rejected",
        ["raw-private-key", "mnemonic", "encrypted-backup"],
        "must be sorted alphabetically",
    )

    print("\n[rejected: type]")
    expect_error("bare string is rejected", "mnemonic", "must be a JSON array or null")
    expect_error("bare number is rejected", 3, "must be a JSON array or null")
    expect_error("object is rejected", {"0": "mnemonic"}, "must be a JSON array or null")

    print("\n[non-wallet rows and message shape]")
    check("non-dict rows are skipped", tool.validate_key_export_formats([None, "x", 4], context=CONTEXT) == [])
    check(
        "row without the key is skipped",
        tool.validate_key_export_formats([{"slug": "a"}], context=CONTEXT) == [],
    )
    errs = run(["seed-phrase"])
    check("no error for a row with no value", run(None) == [])
    check("message names the column", errs and tool.KEY_EXPORT_FORMATS_COLUMN in errs[0], str(errs))
    check("message names the slug", errs and "'demo-wallet'" in errs[0], str(errs))
    check("message carries the category context", errs and CONTEXT in errs[0], str(errs))

    print("\n[multiplicity: violations are reported together, not short-circuited]")
    errs = run(["mnemonic", "mnemonic", "seed-phrase"])
    check("both the duplicate and the unknown name are reported", len(errs) == 2, str(errs))
    check(
        "each problem is reported once",
        len(errs) == len(set(errs)),
        str(errs),
    )
    errs = run(["seed-phrase", "also-bad"])
    check(
        "both invalid entries are reported",
        len(errs) == 2 and all("must be one of" in e for e in errs),
        str(errs),
    )
    errs = run(["seed-phrase", "mnemonic"])
    check(
        "an invalid entry suppresses the order check on the same array",
        len(errs) == 1,
        f"sortedness of a partly-invalid array is noise; got {errs}",
    )

    print("\n[enum contract]")
    check(
        "the documented enum is unchanged",
        tuple(tool.KEY_EXPORT_FORMAT_NAMES) == ("encrypted-backup", "mnemonic", "raw-private-key"),
        str(tool.KEY_EXPORT_FORMAT_NAMES),
    )

    print("\n[wiring: main() must still call the validator and exit non-zero]")
    body = _inspect.getsource(tool.main)
    check("main() calls validate_key_export_formats", "validate_key_export_formats(" in body)
    check(
        "main() rejects the run when the validator reports errors",
        "key_export_format_errors:" in body and "exit(1)" in body,
    )
    check(
        "main() feeds wallets rows into it",
        'result.get("wallets", [])' in body,
        "expected result.get(\"wallets\", []) as the argument",
    )

    print(f"\n{CHECKS - len(FAILURES)}/{CHECKS} checks passed")
    if FAILURES:
        print("FAILED:")
        for f in FAILURES:
            print("  -", f)
        return 1
    print("All keyExportFormats regression checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
