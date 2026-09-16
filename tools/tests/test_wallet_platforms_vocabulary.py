"""Unit tests for the DBIP-3243 controlled vocabulary on wallet supportedPlatforms.

Run from the repository root:  python3 tools/tests/test_wallet_platforms_vocabulary.py

Every assertion is about the two files this PR changes:
  tools/schema.json   - the enum + uniqueItems on $defs/wallets.supportedPlatforms
  meta/columns.json   - the contributor-facing description of the column

The two harvested tables (MIGRATED / MAIN_TREE) are the real distinct values of
the column in the data migration PR #3670 and in current main, so the test also
pins the cross-PR contract: everything #3670 produces is accepted, and the
aliases still present in main are not.
"""
from __future__ import annotations

import json
import pathlib
import sys

from jsonschema import Draft202012Validator

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent

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
    order = {v: i for i, v in enumerate(EXPECTED)}
    for array in MIGRATED:
        row = base_row()
        row["supportedPlatforms"] = list(array)
        errs = messages(validator, row)
        check(f"migrated value {array} is accepted", errs == [])
        check(f"migrated value {array} is deduplicated",
              len(array) == len(set(array)))
        check(f"migrated value {array} is in canonical order",
              [order[v] for v in array] == sorted(order[v] for v in array))

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
