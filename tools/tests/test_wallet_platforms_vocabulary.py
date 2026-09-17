"""Unit tests for the DBIP-3243 controlled vocabulary on wallet supportedPlatforms.

Run from the repository root:  python3 tools/tests/test_wallet_platforms_vocabulary.py

Every assertion is about the three files this PR changes:
  tools/schema.json   - the enum + uniqueItems on $defs/wallets.supportedPlatforms
  meta/columns.json   - the contributor-facing description of the column
  tools/validate.py   - the rule that enforces the canonical storage order

The schema can express membership and uniqueness but not order: an enum plus
uniqueItems accept every permutation of the vocabulary. The ordering half of the
DBIP is therefore enforced by rule_supported_platforms_canonical_order, and the
assertions below pin both halves separately - the schema accepting an
out-of-order array, and the rule rejecting the same array.

The harvested tables hold the real values of the column: MIGRATED and
MAIN_TREE_OUT_OF_VOCABULARY come from the data migration PR #3670 and from
current main, and MAIN_TREE_OUT_OF_ORDER is the subset of main that the enum and
uniqueItems both accept. Together they pin the cross-PR contract in both
directions: everything #3670 produces is accepted, while the aliases and the
orderings still present in main are not.
"""
from __future__ import annotations

import inspect
import json
import pathlib
import sys

from jsonschema import Draft202012Validator

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent

sys.path.insert(0, str(REPO / "tools"))
import validate as repo_validate  # noqa: E402  (needs the path entry above)

EXPECTED = ["Browser Extension", "Web App", "Desktop", "iOS", "Android", "Hardware Device"]

# Values the DBIP retires (issue #3243) plus the browser names it removes from
# the wiki examples.
RETIRED = ["Extension", "Web", "Webapp", "Hardware", "Chrome", "Firefox", "Edge", "Browser"]

# Distinct arrays in the #3670 migration tree (head 94289a92) - must all pass.
MIGRATED = [
    ["Browser Extension", "iOS", "Android"],
    ["iOS", "Android"],
    ["Web App", "iOS", "Android"],
    ["Web App"],
    ["Desktop", "iOS", "Android"],
    ["Browser Extension"],
    ["Browser Extension", "Web App", "iOS", "Android"],
    ["iOS", "Android", "Hardware Device"],
    ["Hardware Device"],
    ["Web App", "Desktop", "iOS", "Android"],
    ["Web App", "iOS"],
    ["Browser Extension", "Desktop", "iOS", "Android"],
    ["Browser Extension", "Web App"],
    ["Browser Extension", "Desktop", "Android"],
    ["Desktop"],
    ["iOS"],
    ["Web App", "Android"],
]

# Distinct arrays in current main - the values below are why it must fail.
MAIN_TREE_OUT_OF_VOCABULARY = {
    "Web": 42,
    "Hardware": 8,
    "Chrome": 2,
    "Extension": 2,
    "Browser": 1,
    "Firefox": 1,
    "Webapp": 1,
}

# In-vocabulary arrays in current main whose order is wrong. The enum and
# uniqueItems both accept these, so the ordering rule is the only check that
# catches them - which is why the ordering half of the DBIP cannot be a schema
# constraint. Harvested from references/offers/wallets.csv on main (107 rows, 3
# cells); the migration branch has none left.
MAIN_TREE_OUT_OF_ORDER = {
    ("iOS", "Android", "Browser Extension"): 2,
    ("iOS", "Android", "Desktop"): 1,
}

FAILURES: list[str] = []
CHECKED = 0


def check(label: str, condition: bool) -> None:
    global CHECKED
    CHECKED += 1
    if condition:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}")
        FAILURES.append(label)


def load_schema() -> dict:
    return json.loads((REPO / "tools" / "schema.json").read_text(encoding="utf-8"))


def wallet_validator(schema: dict) -> Draft202012Validator:
    # Resolve the definition on its own, keeping $defs so internal $refs work.
    return Draft202012Validator(
        {"$defs": schema["$defs"], "$ref": f"#/$defs/wallets"}
    )


def base_row() -> dict:
    """A wallets row that satisfies every other field of the schema."""
    return {
        "slug": "acme-wallet",
        "provider": "Acme",
        "offer": None,
        "actionButtons": None,
        "openSource": True,
        "supportedPlatforms": None,
        "custodial": False,
        "mfa": False,
        "msig": False,
        "hardware": False,
        "keyExport": False,
        "native": False,
        "evm": False,
        "tendermint": False,
        "tokensSupport": None,
        "staking": False,
        "price": "$0",
        "support": None,
        "audit": None,
        "languages": ["EN"],
        "starred": False,
        "tag": None,
    }


def messages(validator: Draft202012Validator, doc: dict) -> list[str]:
    return [e.message for e in validator.iter_errors(doc)]


def rule_of(platforms) -> list[str]:
    """Run the repository ordering rule over a single wallets row."""
    return repo_validate.rule_supported_platforms_canonical_order(
        [{"slug": "acme-wallet", "supportedPlatforms": platforms}]
    )


def main() -> int:
    schema = load_schema()
    wallets = schema["$defs"]["wallets"]
    field = wallets["properties"]["supportedPlatforms"]

    print("schema declaration:")
    check("supportedPlatforms keeps ['array','null'] as its type",
          field.get("type") == ["array", "null"])
    check("uniqueItems is true, so duplicate entries are rejected",
          field.get("uniqueItems") is True)
    check("items are strings", field.get("items", {}).get("type") == "string")
    check("the enum is exactly the DBIP-3243 vocabulary",
          field.get("items", {}).get("enum") == EXPECTED)
    check("the enum is in the DBIP's canonical storage order",
          field.get("items", {}).get("enum") == EXPECTED and EXPECTED[0] == "Browser Extension")
    check("the schema description documents the vocabulary",
          all(v in field.get("description", "") for v in EXPECTED))

    validator = wallet_validator(schema)

    print("\naccepted values:")
    for value in EXPECTED:
        row = base_row()
        row["supportedPlatforms"] = [value]
        check(f"{value!r} is accepted on its own",
              messages(validator, row) == [])
    row = base_row()
    row["supportedPlatforms"] = list(EXPECTED)
    check("all six values together are accepted", messages(validator, row) == [])
    row = base_row()
    row["supportedPlatforms"] = None
    check("a blank cell (null) is still accepted", messages(validator, row) == [])
    row = base_row()
    row["supportedPlatforms"] = []
    check("an empty array is accepted", messages(validator, row) == [])

    print("\nrejected values:")
    for value in RETIRED:
        row = base_row()
        row["supportedPlatforms"] = [value, "iOS"]
        errs = messages(validator, row)
        check(f"{value!r} is rejected as out of vocabulary",
              any("is not one of" in e for e in errs))
    row = base_row()
    row["supportedPlatforms"] = ["browser extension", "iOS"]
    check("the vocabulary is case sensitive",
          any("is not one of" in e for e in messages(validator, row)))
    row = base_row()
    row["supportedPlatforms"] = ["Web App ", "iOS"]
    check("a trailing space is not accepted",
          any("is not one of" in e for e in messages(validator, row)))
    row = base_row()
    row["supportedPlatforms"] = ["iOS", "iOS", "Android"]
    check("duplicate entries are rejected by uniqueItems",
          any("non-unique" in e for e in messages(validator, row)))
    row = base_row()
    row["supportedPlatforms"] = "Desktop"
    check("a bare string instead of an array is rejected",
          any("is not of type" in e for e in messages(validator, row)))
    row = base_row()
    row["supportedPlatforms"] = [5]
    check("a non-string entry is rejected",
          any("is not of type" in e or "is not one of" in e for e in messages(validator, row)))

    print("\nmeta/columns.json:")
    columns = json.loads((REPO / "meta" / "columns.json").read_text(encoding="utf-8"))
    entry = columns["supportedPlatforms"]
    description = entry.get("description", "")
    check("the column still points at supportedPlatforms", entry.get("key") == "supportedPlatforms")
    check("the description no longer says just 'Supported platforms.'",
          description.strip() != "Supported platforms.")
    marker = "One of: "
    check("the description enumerates the allowed values", marker in description)
    listed = (
        description.split(marker, 1)[1].split(" (DBIP", 1)[0].split(", ") if marker in description else []
    )
    check("the description lists exactly the schema enum, in the same order",
          listed == EXPECTED)

    print("\ncross-PR contract with the data migration (#3670):")
    for array in MIGRATED:
        row = base_row()
        row["supportedPlatforms"] = list(array)
        errs = messages(validator, row)
        check(f"migrated value {array} is accepted", errs == [])
        check(f"migrated value {array} is deduplicated",
              len(array) == len(set(array)))
        check(f"migrated value {array} passes the repository ordering rule",
              rule_of(array) == [])

    print("\ncanonical order is enforced by tools/validate.py:")
    # Order is the part of DBIP #3243 that JSON Schema cannot carry. The pair below
    # is the whole argument: the schema on its own accepts an otherwise-valid
    # out-of-order array, and the rule is what rejects it.
    out_of_order = ["Android", "Browser Extension"]
    row = base_row()
    row["supportedPlatforms"] = list(out_of_order)
    check("the schema alone accepts the reviewer's out-of-order example",
          messages(validator, row) == [])
    errors = rule_of(out_of_order)
    check("the repository rule rejects that same array", len(errors) == 1)
    check("the rejection names the whole canonical order",
          bool(errors) and " > ".join(EXPECTED) in errors[0])
    check("the rejection reports the value that was found",
          bool(errors) and str(out_of_order) in errors[0])
    check("the rejection reports the order that was expected",
          bool(errors) and "expected ['Browser Extension', 'Android']" in errors[0])

    check("the full canonical order is accepted", rule_of(list(EXPECTED)) == [])
    check("every value is accepted on its own",
          all(rule_of([value]) == [] for value in EXPECTED))
    check("the migration output is already canonical",
          all(rule_of(array) == [] for array in MIGRATED))

    # A middle swap keeps index 0 correct, so it only fails if the rule compares
    # the whole sequence rather than just looking at the first element.
    middle_swap = ["Browser Extension", "Desktop", "Web App"]
    check("a swap in the middle is rejected", len(rule_of(middle_swap)) == 1)
    check("the middle swap names the canonical order too",
          bool(rule_of(middle_swap))
          and "Browser Extension > Web App > Desktop" in rule_of(middle_swap)[0])
    check("an adjacent swap is rejected",
          len(rule_of(["Browser Extension", "iOS", "Web App", "Desktop", "Android", "Hardware Device"])) == 1)
    check("a fully reversed array is rejected",
          len(rule_of(list(reversed(EXPECTED)))) == 1)

    # The rule reports ordering only: membership stays with the enum, uniqueness
    # with uniqueItems, and types with the schema, so each defect is reported by
    # exactly one check rather than twice.
    check("a blank cell is left to the schema", rule_of(None) == [])
    check("an empty array is left to the schema", rule_of([]) == [])
    check("a bare string is left to the schema", rule_of("Desktop") == [])
    check("a non-string entry is left to the schema", rule_of([5, "iOS"]) == [])
    check("an out-of-vocabulary entry is left to the enum",
          rule_of(["Android", "NotAPlatform"]) == [])
    check("a duplicate is left to uniqueItems", rule_of(["iOS", "iOS"]) == [])
    check("a row without the column is ignored",
          repo_validate.rule_supported_platforms_canonical_order([{"slug": "acme-wallet"}]) == [])
    check("the rule is registered in main(), so validate.py runs it",
          "rules.add_rule(rule_supported_platforms_canonical_order)"
          in inspect.getsource(repo_validate.main))

    print("\nthe ordering defect is real in current main, not hypothetical:")
    for values, cells in MAIN_TREE_OUT_OF_ORDER.items():
        value = list(values)
        canonical = sorted(value, key=EXPECTED.index)
        check(f"{value} ({cells} cells in main) is accepted by the schema",
              (lambda row: messages(validator, row) == [])(
                  {**base_row(), "supportedPlatforms": value}))
        errors = rule_of(value)
        check(f"{value} ({cells} cells in main) is rejected by the rule",
              len(errors) == 1)
        check(f"{value} is reordered to {canonical} in the message",
              bool(errors) and str(canonical) in errors[0])
        check(f"{canonical} is accepted, so the fix the rule asks for is legal",
              rule_of(canonical) == [])

    print("\ncurrent main data is rejected by design:")
    for value in MAIN_TREE_OUT_OF_VOCABULARY:
        row = base_row()
        row["supportedPlatforms"] = [value, "iOS"]
        check(f"{value!r} ({MAIN_TREE_OUT_OF_VOCABULARY[value]} cells in main) is rejected",
              any("is not one of" in e for e in messages(validator, row)))

    print()
    if FAILURES:
        print(f"{len(FAILURES)} of {CHECKED} checks FAILED:")
        for f in FAILURES:
            print("  -", f)
        return 1
    print(f"all {CHECKED} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
