"""Unit tests for the DBIP #3713 extensionBrowsers change (PR #3740).

Run from the repository root:  python3 tools/tests/test_extension_browsers.py

The three files this PR touches are checked both on their own and against each
other, because a schema, a column description and a converter rule that drift
apart is exactly the failure mode the CI is supposed to catch:

  tools/schema.json    - the optional string array and its browser vocabulary
  meta/columns.json    - the contributor-facing description of the column
  tools/csv_to_json.py - validate_extension_browsers() and its wiring into main()
"""
from __future__ import annotations

import json
import pathlib
import sys

from jsonschema import Draft202012Validator

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE.parent))

import csv_to_json  # noqa: E402  (importable only after the path tweak)

COLUMN = "extensionBrowsers"
BROWSERS = ("Brave", "Chrome", "Edge", "Firefox", "Opera", "Safari")
METAMASK = ["Brave", "Chrome", "Edge", "Firefox", "Opera"]
PHANTOM = ["Chrome"]

CHECKED = 0
FAILURES: list[str] = []


def check(label: str, condition: bool) -> None:
    global CHECKED
    CHECKED += 1
    if condition:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}")
        FAILURES.append(label)


def row(value, slug="demo-wallet"):
    """A row carrying every key $defs/wallets marks as required, plus the column."""
    full = {
        "slug": slug,
        "provider": "Acme",
        "openSource": False,
        "supportedPlatforms": ["Web"],
        "custodial": False,
        "mfa": False,
        "msig": False,
        "hardware": False,
        "keyExport": False,
        "native": False,
        "evm": True,
        "tendermint": False,
        "tokensSupport": ["ETH"],
        "staking": False,
        "price": "$0",
        "support": ["[website](https://example.com/support)"],
        "audit": None,
        "languages": ["EN"],
        "starred": False,
        "actionButtons": ["[Website](https://example.com/)"],
        "tag": ["Wallet"],
    }
    full[COLUMN] = value
    return full


def errors(value):
    return csv_to_json.validate_extension_browsers([row(value)], context="unit")


def has(value, needle):
    return any(needle in e for e in errors(value))


# ---------------------------------------------------------------------------
print("schema.json: the column is declared on $defs/wallets and nowhere else")
schema = json.loads((REPO / "tools" / "schema.json").read_bytes().decode("utf-8"))
wallets = schema["$defs"]["wallets"]
# .get() throughout: a mutation that removes the property or its enum must make
# these checks fail, not raise, or the mutation test would pass for the wrong
# reason.
prop = wallets["properties"].get(COLUMN, {})
items = prop.get("items", {})
check("extensionBrowsers is a wallets property", COLUMN in wallets["properties"])
check("type is [array, null]", prop.get("type") == ["array", "null"])
check("items are strings", items.get("type") == "string")
check("items are restricted to the browser vocabulary",
      items.get("enum") == list(BROWSERS))
check("entries must be unique", prop.get("uniqueItems") is True)
check("the column is optional", COLUMN not in wallets["required"])
check("wallets requires the same 21 keys as before",
      set(wallets["required"]) == {
          "slug", "provider", "openSource", "supportedPlatforms", "custodial",
          "mfa", "msig", "hardware", "keyExport", "native", "evm", "tendermint",
          "tokensSupport", "staking", "price", "support", "audit", "languages",
          "starred", "actionButtons", "tag"})
check("wallets still closes additionalProperties", wallets["additionalProperties"] is False)
keys = list(wallets["properties"])
check("the empty array is allowed by the schema ([] is an explicit value)",
      prop["type"] == ["array", "null"])
check("the column sits between languages and starred",
      (keys[keys.index(COLUMN) - 1], keys[keys.index(COLUMN) + 1]) == ("languages", "starred"))
other_defs = [n for n, d in schema["$defs"].items()
              if n != "wallets" and COLUMN in d.get("properties", {})]
check("no other category declares the column", other_defs == [])
check("the removed verified* columns stay removed",
      all("verifiedUptime" not in d.get("properties", {}) for d in schema["$defs"].values()))

print("schema.json: a valid array and an invalid one behave as declared")
validator = Draft202012Validator(schema).evolve(schema=wallets)
check("the MetaMask vocabulary validates", validator.is_valid(row(METAMASK)))
check("the Phantom vocabulary validates", validator.is_valid(row(PHANTOM)))
check("blank stays valid", validator.is_valid(row(None)))
check("an explicit empty array is valid", validator.is_valid(row([])))
check("an unknown browser is rejected", not validator.is_valid(row(["Chrome", "Gecko"])))
check("a lowercase alias is rejected", not validator.is_valid(row(["chrome"])))
check("a duplicate entry is rejected", not validator.is_valid(row(["Chrome", "Chrome"])))
check("a non-array value is rejected", not validator.is_valid(row({"browser": "Chrome"})))
check("a string value is rejected", not validator.is_valid(row("Chrome")))
check("a non-string entry is rejected", not validator.is_valid(row(["Chrome", 7])))

# ---------------------------------------------------------------------------
print("meta/columns.json: the column is described for contributors")
columns = json.loads((REPO / "meta" / "columns.json").read_bytes().decode("utf-8"))
check("extensionBrowsers is described", COLUMN in columns)
meta = columns.get(COLUMN, {})
check("key matches the column name", meta.get("key") == COLUMN)
check("label is human readable", meta.get("label") == "Extension Browsers")
check("description mentions desktop browsers", "desktop browsers" in meta.get("description", "").lower())
check("description mentions first-party support", "supported wallet extension" in meta.get("description", ""))
check("icon is set", meta.get("icon") == "lucide:Puzzle")
check("filter is searchableMultiSelect", meta.get("filter") == "searchableMultiSelect")
check("sorting is arrayLength", meta.get("sorting") == "arrayLength")
check("cellType is arrayPopover", meta.get("cellType") == "arrayPopover")
check("group is capabilities", meta.get("group") == "capabilities")
check("the column sits between keyExport and native",
      (list(columns).index(COLUMN) - 1, list(columns).index(COLUMN) + 1)
      == (list(columns).index("keyExport"), list(columns).index("native")))
check("the descriptor reappears nowhere else in the table",
      sum(1 for k, v in columns.items() if v.get("key") == COLUMN) == 1)
check("the removed verified* descriptors stay removed",
      all("verifiedUptime" not in k for k in columns))

# ---------------------------------------------------------------------------
print("csv_to_json.py: the vocabulary is shared with the schema")
check("EXTENSION_BROWSERS_COLUMN", csv_to_json.EXTENSION_BROWSERS_COLUMN == COLUMN)
check("EXTENSION_BROWSER_NAMES", csv_to_json.EXTENSION_BROWSER_NAMES == BROWSERS)
check("schema and converter agree on the vocabulary",
      list(csv_to_json.EXTENSION_BROWSER_NAMES) == items.get("enum"))

print("csv_to_json.py: validate_extension_browsers() accepts what it should")
check("blank is accepted (unknown)", errors(None) == [])
check("a row without the column is accepted",
      csv_to_json.validate_extension_browsers([{"slug": "x"}], context="unit") == [])
check("an empty array is accepted", errors([]) == [])
check("the MetaMask example is accepted", errors(METAMASK) == [])
check("the Phantom example is accepted", errors(PHANTOM) == [])
check("a single browser is accepted", errors(["Firefox"]) == [])
check("a two-browser array in order is accepted", errors(["Chrome", "Firefox"]) == [])
check("the vocabulary is accepted in full", errors(list(BROWSERS)) == [])
check("a trailing empty cell never reaches the validator as ''",
      csv_to_json.normalize({"wallets": [{COLUMN: ""}]})
      == ({"wallets": [{COLUMN: None}]}, []))
check("a JSON array cell is parsed before validation",
      csv_to_json.normalize({"wallets": [{COLUMN: '["Chrome","Firefox"]'}]})
      == ({"wallets": [{COLUMN: ["Chrome", "Firefox"]}]}, []))

print("csv_to_json.py: each rule of DBIP #3713 rejects on its own")
check("unknown browser", has(["Chrome", "Gecko"], "must be one of"))
check("lowercase alias", has(["chrome"], "must be one of"))
check("uppercase alias", has(["CHROME"], "must be one of"))
check("duplicate entry", has(["Chrome", "Chrome"], "duplicates browser"))
check("unsorted array", has(["Chrome", "Brave"], "must be sorted alphabetically"))
check("unsorted three-entry array", has(["Edge", "Brave", "Chrome"], "must be sorted alphabetically"))
check("a JSON object is not an array",
      has({"browser": "Chrome"}, "must be a JSON array or null, got dict"))
check("a bare string is not an array",
      has("Chrome", "must be a JSON array or null, got str"))
check("a number is not an array",
      has(7, "must be a JSON array or null, got int"))
check("a non-string entry", has(["Chrome", 7], "must be one of"))
check("a null entry", has(["Chrome", None], "must be one of"))
check("the offending row is named", has(["chrome"], "wallets 'demo-wallet'"))
check("the offending position is named", has(["Chrome", "Gecko"], f"{COLUMN}[1]"))
check("a later bad entry is still reported", has(["Chrome", "Edge", "nope"], f"{COLUMN}[2]"))
check("an invalid name is reported even when the array is also unsorted",
      has(["Chrome", "Gecko", "Brave"], "must be one of"))
check("a sorted array is never reported as unsorted",
      errors(["Brave", "Chrome", "Edge", "Firefox", "Opera", "Safari"]) == [])

# ---------------------------------------------------------------------------
print("csv_to_json.py: the validator is wired into the network pass of main()")
src = (REPO / "tools" / "csv_to_json.py").read_bytes().decode("utf-8")
check("the wallets rows of every network are validated",
      "extension_browser_errors = validate_extension_browsers(" in src)
check("the validator receives the resolved wallets of the network",
      'result.get("wallets", [])' in src)
check("the network pass names the network", "context=f\"network '{network_name}'\"" in src)
check("the network pass exits on error", "if extension_browser_errors:" in src)
check("the failure names the column",
      'Validation errors for {EXTENSION_BROWSERS_COLUMN} in network' in src)

# ---------------------------------------------------------------------------
print()
print(f"{CHECKED} checks, {len(FAILURES)} failures")
if FAILURES:
    for f in FAILURES:
        print(f"  - {f}")
    sys.exit(1)
print("OK")
