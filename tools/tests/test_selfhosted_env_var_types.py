"""Unit tests for the DBIP #3683 selfHostedEnvVarTypes change (PR #3698).

Run from the repository root:  python3 tools/tests/test_selfhosted_env_var_types.py

The three files this PR touches are checked both on their own and against each
other, because a schema, a column description and a converter rule that drift
apart is exactly the failure mode the CI is supposed to catch:

  tools/schema.json    - the optional object + its six-label enum
  meta/columns.json    - the contributor-facing description of the column
  tools/csv_to_json.py - duplicate-member rejection and the resolved-row rules
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

COLUMN = "selfHostedEnvVarTypes"
LABELS = [
    "api-key",
    "wallet-private-key",
    "wallet-mnemonic",
    "access-token",
    "other-secret",
    "non-secret",
]

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


def base_row(**overrides) -> dict:
    row = {
        "slug": "demo-mcp",
        "provider": "Acme",
        "actionButtons": ["[Docs](https://example.com/docs)"],
        "serverType": "services",
        "hostingType": "Self-hosted",
        "transportType": "stdio",
        "mcpEndpoint": None,
        "authType": "None",
        "credentialKey": None,
        "selfHostedCommand": "npx",
        "selfHostedArgs": ["-y", "@acme/mcp"],
        "selfHostedRequiredEnvVars": ["PRIVATE_KEY"],
        "x402": False,
        "onChainWrite": False,
        "agentSkills": ["file-upload"],
        "tag": ["AI agents"],
        "description": "Demo MCP server.",
        "planType": "Freemium",
        "planName": None,
        "price": "Usage-based",
        "trial": False,
        "starred": False,
    }
    row.update(overrides)
    return row


def messages(validator, row: dict) -> list[str]:
    return [e.message for e in validator.iter_errors(row)]


def main() -> int:
    schema = json.loads((REPO / "tools" / "schema.json").read_text(encoding="utf-8"))
    columns = json.loads((REPO / "meta" / "columns.json").read_text(encoding="utf-8"))
    converter_src = (REPO / "tools" / "csv_to_json.py").read_text(encoding="utf-8")

    mcpservers = schema["$defs"]["mcpservers"]
    field = mcpservers["properties"].get(COLUMN)

    print("tools/schema.json:")
    check(f"{COLUMN} exists on $defs/mcpservers", field is not None)
    if field is None:
        print("\nFATAL: the schema change is missing")
        return 1
    check("it is nullable", field.get("type") == ["object", "null"])
    check("it is optional (not in required)", COLUMN not in mcpservers.get("required", []))
    check("member values are restricted to the DBIP-3683 vocabulary",
          field.get("additionalProperties", {}).get("enum") == LABELS)
    check("member names must be non-empty strings",
          field.get("propertyNames") == {"type": "string", "minLength": 1})
    check("mcpservers forbids undeclared properties, so the column must be added here",
          mcpservers.get("additionalProperties") is False)
    check("the legacy selfHostedRequiredEnvVars field is untouched",
          mcpservers["properties"]["selfHostedRequiredEnvVars"]
          == {"type": ["array", "null"], "items": {"type": "string"}})

    validator = Draft202012Validator(
        {"$ref": f"#/$defs/mcpservers", "$defs": schema["$defs"]}
    )
    print("\nschema behaviour:")
    check("null (unclassified legacy row) is accepted",
          messages(validator, base_row()) == [])
    check("an explicitly empty map is accepted",
          messages(validator, base_row(**{COLUMN: {}})) == [])
    for label in LABELS:
        check(f"label {label!r} is accepted",
              messages(validator, base_row(**{COLUMN: {"PRIVATE_KEY": label}})) == [])
    check("a partial map is accepted",
          messages(validator, base_row(
              selfHostedRequiredEnvVars=["A", "B"], **{COLUMN: {"A": "api-key"}})) == [])
    check("an empty member name is rejected",
          any("minLength" in m or "''" in m or "too short" in m
              for m in messages(validator, base_row(**{COLUMN: {"": "api-key"}}))))
    check("an undeclared label is rejected",
          any("is not one of" in m
              for m in messages(validator, base_row(**{COLUMN: {"PRIVATE_KEY": "secret"}}))))
    check("label casing matters",
          any("is not one of" in m
              for m in messages(validator, base_row(**{COLUMN: {"PRIVATE_KEY": "API-KEY"}}))))
    for bad in (["api-key"], "api-key", 42, True):
        check(f"a {type(bad).__name__} cell is rejected",
              any("is not of type" in m
                  for m in messages(validator, base_row(**{COLUMN: bad}))))

    print("\nmeta/columns.json:")
    meta = columns.get(COLUMN)
    check("the column is documented", meta is not None)
    if meta is not None:
        check("the key matches the column name", meta.get("key") == COLUMN)
        check("it is grouped with the other self-hosting security fields",
              meta.get("group") == "security")
        description = meta.get("description", "")
        check("the description enumerates the allowed labels",
              all(label in description for label in LABELS))
        check("the description lists them in the schema order",
              [description.index(label) for label in LABELS]
              == sorted(description.index(label) for label in LABELS))
        check("the description states that partial maps are allowed",
              "Partial maps" in description)
        check("the description states that omitted variables are unclassified",
              "unclassified" in description)

    print("\ntools/csv_to_json.py:")
    check("the column constant matches the schema property",
          csv_to_json.ENV_VAR_TYPES_COLUMN == COLUMN)
    check("the label tuple matches the DBIP vocabulary",
          list(csv_to_json.ENV_VAR_TYPE_LABELS) == LABELS)
    check("the converter labels and the schema enum cannot drift apart",
          list(csv_to_json.ENV_VAR_TYPE_LABELS)
          == field["additionalProperties"]["enum"])

    try:
        parsed = csv_to_json.parse_json_object_no_duplicates('{"A":"api-key","B":"non-secret"}')
        check("a well-formed map parses", parsed == {"A": "api-key", "B": "non-secret"})
    except Exception as e:  # pragma: no cover - the assertion is the point
        check(f"a well-formed map parses (raised {e!r})", False)
    try:
        csv_to_json.parse_json_object_no_duplicates('{"A":"api-key","A":"non-secret"}')
        check("duplicate members are rejected", False)
    except ValueError as e:
        check("duplicate members are rejected", "duplicate object member" in str(e))

    def errors(**overrides) -> list[str]:
        return csv_to_json.validate_selfhosted_env_var_types(
            [base_row(**overrides)], context="references/offers"
        )

    check("an absent map is left alone",
          errors() == [])
    check("an explicit empty map is always valid",
          errors(**{COLUMN: {}}) == [])
    check("an empty map is valid even on a hosted row",
          errors(hostingType="Hosted", **{COLUMN: {}}) == [])
    check("a partial map is valid",
          errors(selfHostedRequiredEnvVars=["A", "B"], **{COLUMN: {"A": "api-key"}}) == [])
    check("all six labels together are valid",
          errors(selfHostedRequiredEnvVars=["A", "B", "C", "D", "E", "F"],
                 **{COLUMN: {name: label for name, label in
                             zip("ABCDEF", LABELS)}}) == [])
    check("an undeclared variable name is rejected",
          any("is not declared in the resolved" in e
              for e in errors(**{COLUMN: {"NOT_DECLARED": "api-key"}})))
    check("name matching is case-sensitive",
          any("is not declared" in e for e in errors(**{COLUMN: {"private_key": "api-key"}})))
    check("the exact declared name is accepted",
          errors(**{COLUMN: {"PRIVATE_KEY": "api-key"}}) == [])
    check("an unsupported label is rejected",
          any("unsupported label" in e
              for e in errors(**{COLUMN: {"PRIVATE_KEY": "secret"}})))
    check("a non-empty map on a hosted row is rejected",
          any("only valid when hostingType is 'Self-hosted'" in e
              for e in errors(hostingType="Hosted", **{COLUMN: {"PRIVATE_KEY": "api-key"}})))
    check("a non-object cell is rejected",
          any("must be a JSON object" in e for e in errors(**{COLUMN: ["api-key"]})))
    check("a map without a required-variable list is rejected",
          any("is not declared" in e
              for e in errors(selfHostedRequiredEnvVars=None,
                              **{COLUMN: {"PRIVATE_KEY": "api-key"}})))
    both = errors(**{COLUMN: {"OTHER": "nope"}})
    check("every problem in a map is reported, not just the first", len(both) == 2)
    check("the context names the failing table", all("references/offers" in e for e in both))
    check("non-dict rows are skipped instead of crashing",
          csv_to_json.validate_selfhosted_env_var_types(["oops"], context="x") == [])

    print("\nthe converter is wired into the pipeline:")
    calls = converter_src.count("validate_selfhosted_env_var_types(")
    check("the rules run for offers and for every network", calls >= 3)
    check("they run after !offer: resolution",
          converter_src.index("result = resolve_offers(")
          < converter_src.rindex("validate_selfhosted_env_var_types("))
    check("duplicate members are checked before ordinary JSON parsing",
          "parse_json_object_no_duplicates(new_item[key])" in converter_src)

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
