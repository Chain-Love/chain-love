"""Regression tests for validate_key_export_formats (DBIP #3725).

One case per documented rule, plus the wiring assertion that makes the negative
controls in CI meaningful: the unit cases call the function directly, so they
cannot notice the call being removed from main().

Run: python3 tools/tests/test_key_export_formats.py
"""
from __future__ import annotations

import csv
import inspect as _inspect
import io
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import csv_to_json as tool  # noqa: E402
import jsonschema  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[2]
FIXTURES = REPO / "tools" / "tests" / "fixtures" / "key-export-formats"

# The schema half of the two-layer story. validate.py validates references/offers through
# make_providers_schema, so the enum, the uniqueness and the entry type are covered for
# every canonical row whether or not a listing references it. Array order is the one rule
# JSON Schema cannot express, and this table is what pins that claim instead of asserting
# it in prose: a row where the schema says yes and the rule says no is the whole reason
# validate_key_export_formats is reachable from two call sites.
_ROOT_SCHEMA = json.loads((REPO / "tools" / "schema.json").read_text(encoding="utf-8"))
_COLUMN_SCHEMA = _ROOT_SCHEMA["$defs"]["wallets"]["properties"]["keyExportFormats"]
_COLUMN_VALIDATOR = jsonschema.validators.validator_for(_ROOT_SCHEMA)(_COLUMN_SCHEMA)

# value, schema accepts, rule accepts
LAYER_TABLE = [
    (["mnemonic", "encrypted-backup"], True, False),
    (["raw-private-key", "mnemonic"], True, False),
    (["raw-private-key", "encrypted-backup", "mnemonic"], True, False),
    (["encrypted-backup", "mnemonic"], True, True),
    (["mnemonic"], True, True),
    ([], True, True),
    (None, True, True),
    (["mnemonic", "mnemonic"], False, False),
    (["seed-phrase"], False, False),
    ("mnemonic", False, False),
]

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

    print("\n[schema vs rule: the order check is the one JSON Schema cannot carry]")
    for value, schema_ok, rule_ok in LAYER_TABLE:
        check(
            f"schema {'accepts' if schema_ok else 'rejects'} {value!r}",
            _COLUMN_VALIDATOR.is_valid(value) == schema_ok,
            f"schema verdict disagrees with the table for {value!r}",
        )
        check(
            f"rule {'accepts' if rule_ok else 'rejects'} {value!r}",
            (errors_for(value) == []) == rule_ok,
            str(errors_for(value)),
        )
    schema_blind = [v for v, s, r in LAYER_TABLE if s and not r]
    check(
        "three values are accepted by the schema and rejected by the rule",
        len(schema_blind) == 3,
        f"the rule would be redundant with the schema unless this is non-empty; got {schema_blind}",
    )

    print("\n[the CI fixture carries exactly that value]")
    fixture = FIXTURES / "offers.wallets.negative-unreferenced-unsorted.csv"
    raw = fixture.read_bytes().decode("utf-8")
    rows = list(csv.reader(io.StringIO(raw)))
    cols = rows[0]
    body = rows[1:]
    check("the fixture has two rows: one referenced, one not", len(body) == 2, str(len(body)))
    check(
        "the fixture's slugs are ascending (validate_csv.py walks this tree)",
        [r[0] for r in body] == sorted(r[0] for r in body),
        str([r[0] for r in body]),
    )
    referenced = [r for r in body if r[0] == "demo-offer"]
    check(
        "the first row is the canonical offer the listing references",
        len(referenced) == 1 and referenced[0][cols.index("offer")] == "",
        "demo-offer must stay byte-identical to the valid fixture",
    )
    assert len(body) == 2, body
    payload = json.loads(body[1][cols.index("keyExportFormats")])
    check(
        "the second row is unreferenced and unsorted but in vocabulary and unique",
        body[1][0] == "zzz-unreferenced-wallet" and payload == ["mnemonic", "encrypted-backup"],
        f"{body[1][0]} {payload!r}",
    )
    check(
        "the fixture value is in the schema-blind set",
        payload in schema_blind,
        f"{payload!r} is not in {schema_blind}",
    )
    check(
        "the fixture value trips the order rule and nothing else",
        len(errors_for(payload)) == 1 and "must be sorted alphabetically" in errors_for(payload)[0],
        str(errors_for(payload)),
    )

    print("\n[canonical context: the message must name the offers file it read]")
    errs = run(["mnemonic", "encrypted-backup"], context="references/offers")
    check(
        "the canonical context reaches the message",
        errs and errs[0].startswith("references/offers: wallets 'demo-wallet'"),
        str(errs),
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
    check(
        "main() calls the validator at two call sites",
        body.count("validate_key_export_formats(") == 2,
        f"expected the canonical row and the network row; got {body.count('validate_key_export_formats(')}",
    )
    check(
        "the second call site reads the canonical offers, not a resolved network result",
        'offers_by_category.get("wallets", [])' in body,
        "expected offers_by_category.get(\"wallets\", []) as the argument",
    )
    check(
        "each call site exits non-zero on its own error list",
        body.count("exit(1)") >= 2 and "offer_key_export_format_errors:" in body,
        "the canonical errors must abort the run, not just be printed",
    )
    check(
        "the canonical call site is labelled references/offers",
        'context="references/offers"' in body,
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
