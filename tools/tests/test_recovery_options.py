"""Regression tests for validate_recovery_options (DBIP #4412).

One case per documented rule, plus the wiring assertion that makes the negative
controls meaningful: the unit cases call the function directly, so they cannot
notice the call being removed from resolve_offers().

Run: python3 tools/tests/test_recovery_options.py
"""
from __future__ import annotations

import csv as _csv
import io
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import csv_to_json as tool  # noqa: E402
import jsonschema  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[2]
FIXTURES = REPO / "tools" / "tests" / "fixtures" / "recovery-options"

# The schema half of the two-layer story. validate.py validates every bridge row
# through the published schema, so the enum, the uniqueness, the minimum length
# and the URL shape are all covered for real data. The validator adds the
# slug-scoped, human-readable failure path and the "absent is not unsupported"
# semantics the schema cannot express as an error message.
_ROOT = json.loads((REPO / "tools" / "schema.json").read_text(encoding="utf-8"))
_COLUMN_SCHEMA = _ROOT["$defs"]["bridges"]["properties"]["recoveryOptions"]
_COLUMN_VALIDATOR = jsonschema.validators.validator_for(_ROOT)(_COLUMN_SCHEMA)

NETWORK = "demo"
CATEGORY = "bridges"
CONTEXT = f"{NETWORK}/{CATEGORY}"

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


def run(value, *, present: bool = True, slug: str = "demo-bridge", network: str = NETWORK, category: str = CATEGORY):
    """Call the validator with one bridge row and return the error list."""
    item = {"slug": slug} if present else {}
    if present:
        item[tool.RECOVERY_OPTIONS_COLUMN] = value
    return tool.validate_recovery_options([item], network_name=network, category=category)


def expect_ok(label: str, value, *, present: bool = True) -> None:
    errs = run(value, present=present)
    check(label, errs == [], f"expected no errors, got {errs}")


def expect_error(label: str, value, needle: str) -> None:
    errs = run(value)
    joined = "\n".join(errs)
    check(
        label,
        len(errs) >= 1 and needle in joined,
        f"expected an error containing {needle!r}, got {errs}",
    )


def valid_option(**over):
    base = {
        "failureCase": "unfilled-expired",
        "mechanism": "protocol-refund",
        "scopeNote": "Refund is broadcast by the protocol if the HTLC is not "
                     "filled within the 24h timeout; user pays only gas.",
        "sourceUrl": "https://docs.example.bridge/refunds",
    }
    base.update(over)
    return base


def main() -> int:
    print("validate_recovery_options - rule coverage")

    print("\n[accepted]")
    expect_ok("blank cell (key absent) is accepted", None, present=False)
    expect_ok("explicit null is accepted", None)
    expect_ok("one well-formed option is accepted", [valid_option()])
    expect_ok(
        "two distinct options are accepted",
        [
            valid_option(mechanism="permissionless-retry"),
            valid_option(failureCase="destination-execution-failed", mechanism="user-initiated-claim"),
        ],
    )

    print("\n[rejected: structure]")
    expect_error("empty array is rejected", [], "is an empty array")
    expect_error("bare string is rejected", "not a list", "must be a JSON array")
    expect_error("bare number is rejected", 3, "must be a JSON array")
    expect_error("array with non-object entry is rejected", ["x"], "must be a JSON object")

    print("\n[rejected: required fields]")
    bad = valid_option()
    del bad["scopeNote"]
    expect_error("missing scopeNote is rejected", [bad], "missing the required 'scopeNote'")
    bad = valid_option()
    del bad["sourceUrl"]
    expect_error("missing sourceUrl is rejected", [bad], "missing the required 'sourceUrl'")
    bad = valid_option()
    del bad["failureCase"]
    expect_error("missing failureCase is rejected", [bad], "missing the required 'failureCase'")
    bad = valid_option()
    del bad["mechanism"]
    expect_error("missing mechanism is rejected", [bad], "missing the required 'mechanism'")

    print("\n[rejected: enums]")
    expect_error("unknown failureCase is rejected", [valid_option(failureCase="broken")], "is not one of")
    expect_error("near-miss failureCase is rejected", [valid_option(failureCase="unfilled_expired")], "is not one of")
    expect_error("unknown mechanism is rejected", [valid_option(mechanism="magic")], "is not one of")

    print("\n[rejected: scopeNote]")
    expect_error("short scopeNote is rejected", [valid_option(scopeNote="too short")], "characters")
    expect_error(
        "whitespace-only scopeNote is rejected",
        [valid_option(scopeNote="                    ")],
        "whitespace only",
    )

    print("\n[rejected: duplicates]")
    expect_error(
        "exact duplicate option is rejected",
        [valid_option(), valid_option()],
        "duplicates",
    )
    # Same failureCase + scopeNote but a different mechanism is a distinct remedy,
    # not a duplicate -- the schema's uniqueItems compares whole objects too.
    expect_ok(
        "same failure case with distinct mechanism is accepted",
        [valid_option(mechanism="permissionless-retry"), valid_option(mechanism="user-initiated-claim")],
    )

    print("\n[non-bridge rows and message shape]")
    check(
        "non-dict rows are skipped",
        tool.validate_recovery_options([None, "x", 4], network_name=NETWORK, category=CATEGORY) == [],
    )
    check(
        "row without the key is skipped",
        tool.validate_recovery_options([{"slug": "a"}], network_name=NETWORK, category=CATEGORY) == [],
    )
    errs = run([valid_option(mechanism="magic")])
    check("message names the column", errs and tool.RECOVERY_OPTIONS_COLUMN in errs[0], str(errs))
    check("message names the slug", errs and "demo-bridge" in errs[0], str(errs))
    check("message carries the network/category context", errs and CONTEXT in errs[0], str(errs))

    print("\n[multiplicity: violations are reported together, not short-circuited]")
    bad = valid_option()
    del bad["scopeNote"]
    bad2 = valid_option()
    del bad2["sourceUrl"]
    errs = tool.validate_recovery_options(
        [{"slug": "a", tool.RECOVERY_OPTIONS_COLUMN: [bad, bad2]}],
        network_name=NETWORK,
        category=CATEGORY,
    )
    check("two malformed options each report their own missing field", len(errs) == 2, str(errs))
    check("each problem is reported once", len(errs) == len(set(errs)), str(errs))

    print("\n[enum contract]")
    check(
        "the documented failureCase enum is unchanged",
        tuple(tool.FAILURE_CASES)
        == ("unfilled-expired", "destination-execution-failed", "execution-expired", "other-documented"),
        str(tool.FAILURE_CASES),
    )
    check(
        "the documented mechanism enum is unchanged",
        tuple(tool.RECOVERY_MECHANISMS)
        == ("protocol-refund", "permissionless-retry", "user-initiated-claim"),
        str(tool.RECOVERY_MECHANISMS),
    )
    check("scopeNote minimum length is 20", tool.SCOPE_NOTE_MIN_LENGTH == 20, str(tool.SCOPE_NOTE_MIN_LENGTH))

    print("\n[schema vs rule: the two layers must agree on the shared rules]")
    vectors = [
        ([valid_option()], True, True),
        ([], False, False),  # minItems
        ([valid_option(), valid_option()], False, False),  # uniqueItems
        ([valid_option(failureCase="bogus")], False, False),  # enum
        ([valid_option(scopeNote="too short")], False, False),  # minLength
        ([valid_option(sourceUrl="http://example.com")], False, True),  # schema: bad URL; rule: URL shape is schema's job
    ]
    for value, schema_ok, rule_ok in vectors:
        check(
            f"schema {'accepts' if schema_ok else 'rejects'} {value!r}",
            _COLUMN_VALIDATOR.is_valid(value) == schema_ok,
            f"schema verdict disagrees for {value!r}",
        )
        check(
            f"rule {'accepts' if rule_ok else 'rejects'} {value!r}",
            (run(value) == []) == rule_ok,
            str(run(value)),
        )
    rule_only = [v for v, s, r in vectors if (not s) and r]
    check(
        "exactly one vector is rejected by the schema but accepted by the rule",
        len(rule_only) == 1 and rule_only[0][0]["sourceUrl"].startswith("http://"),
        f"the rule leaves URL-shape validation to the schema; got {rule_only}",
    )

    print("\n[wiring: resolve_offers must still call the validator and raise on bad data]")
    import inspect as _inspect
    body = _inspect.getsource(tool.resolve_offers)
    check("resolve_offers calls validate_recovery_options", "validate_recovery_options(" in body)
    check(
        "resolve_offers raises ValueError on invalid recoveryOptions",
        "Invalid recoveryOptions for network" in body,
    )
    # End-to-end through the build path with a single valid bridge row.
    good = tool.resolve_offers(
        {"bridges": [{"slug": "demo-bridge", "name": "Demo", tool.RECOVERY_OPTIONS_COLUMN: [valid_option()]}]},
        offers_by_category={},
        network_name=NETWORK,
    )
    check("resolve_offers passes a valid recoveryOptions row through", good["bridges"][0]["slug"] == "demo-bridge")
    try:
        tool.resolve_offers(
            {"bridges": [{"slug": "bad-bridge", "name": "Bad", tool.RECOVERY_OPTIONS_COLUMN: [valid_option(mechanism="magic")]}]},
            offers_by_category={},
            network_name=NETWORK,
        )
        check("resolve_offers raises on an invalid recoveryOptions row", False, "no ValueError raised")
    except ValueError as exc:
        check("resolve_offers raises ValueError naming the column", "recoveryOptions" in str(exc), str(exc))

    print("\n[fixture benchmark: real-shaped CSV rows]")
    valid_csv = FIXTURES / "bridges.valid.csv"
    if valid_csv.exists():
        rows = list(_csv.DictReader(io.StringIO(valid_csv.read_text(encoding="utf-8"))))
        parsed = []
        for r in rows:
            item = {k: v for k, v in r.items() if k}
            raw = item.get(tool.RECOVERY_OPTIONS_COLUMN, "")
            if raw and raw.strip():  # mirrors normalize(): empty/blank -> None -> skipped
                item[tool.RECOVERY_OPTIONS_COLUMN] = json.loads(raw)
            else:
                item.pop(tool.RECOVERY_OPTIONS_COLUMN, None)
            parsed.append(item)
        errs = tool.validate_recovery_options(parsed, network_name=NETWORK, category=CATEGORY)
        check("the valid fixture produces zero validator errors", errs == [], str(errs))
    else:
        print(f"  (skipped: {valid_csv} not found)")

    print(f"\n{CHECKS - len(FAILURES)}/{CHECKS} checks passed")
    if FAILURES:
        print("FAILED:")
        for f in FAILURES:
            print("  -", f)
        return 1
    print("All recoveryOptions regression checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
