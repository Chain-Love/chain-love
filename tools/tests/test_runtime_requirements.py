"""Unit regression tests for validate_runtime_requirements() (DBIP #3751).

Runs with plain `python3` (no pytest) so the required `validate` check can call
it directly inside the network-disabled container.

Coverage intent: the CI job also drives the real pipeline over fixtures, but those
exercise the happy path plus one rejected value per rule. These cases pin down each
individual rule of the validator, so a regression names the rule that broke instead
of just turning the job red.

Two things fixtures cannot show on their own are asserted structurally here:
  * both call sites must exist in main(), because the canonical one is the only place
    an offer that no listing references is ever validated;
  * the `source` URL pattern must be identical in tools/schema.json and in this module,
    because the two layers reject the same values for different reasons and drift
    between them is silent.
"""
import inspect
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
# Assembled CI workspace: csv_to_json.py and schema.json are copied to the repo root.
# Local checkout: they live next to this file's parent (tools/).
sys.path.insert(0, str(HERE.parent.parent))
sys.path.insert(0, str(HERE.parent))

import csv_to_json  # noqa: E402  (path set up above on purpose)

VALID_PY_SOURCE = "https://github.com/algorandfoundation/algokit-utils-py/releases/tag/v4.2.3"
VALID_NODE_SOURCE = "https://github.com/algorandfoundation/algokit-utils-ts/releases/tag/v9.2.2"

FAILURES = []


def check(name, condition, detail=""):
    if condition:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}{(': ' + detail) if detail else ''}")
        FAILURES.append(name)


def errors_for(value):
    """Run the validator over a single sdks row carrying `runtimeRequirements`."""
    row = {"slug": "algokit-utils-py"}
    if value is not _MISSING:
        row["runtimeRequirements"] = value
    return csv_to_json.validate_runtime_requirements([row], context="test")


class _Missing:
    pass


_MISSING = _Missing()


def load_schema():
    """The schema.json the pipeline is actually using: assembled root first, then tools/."""
    for candidate in (HERE.parent.parent / "schema.json", HERE.parent / "schema.json"):
        if candidate.is_file():
            return json.loads(candidate.read_bytes().decode("utf-8")), candidate
    raise SystemExit("schema.json not found next to the checkout root or tools/")


# Verdicts for the `source` rule. `url` means the value must be rejected by the URL rule;
# `empty` means the blankness rule rejects it first and the message must stay the old one, so
# the two rules cannot be collapsed into one. The whole table is replayed against the
# schema.json pattern, so a divergence between the two layers fails here instead of silently
# weakening one of them.
SOURCE_URL_TABLE = [
    ("ok", "https://github.com/algorandfoundation/algokit-utils-py/blob/v4.2.3/pyproject.toml"),
    ("ok", "http://example.com/pyproject.toml"),
    ("ok", "HTTPS://EXAMPLE.COM/pyproject.toml"),
    ("ok", "https://example.com"),
    ("ok", "https://example.com:8443/pyproject.toml?a=b#c"),
    ("ok", "https://192.168.1.1/pyproject.toml"),
    ("ok", "https://a.b-c.d/pyproject.toml"),
    ("url", "not-a-url"),
    ("url", "github.com/algorandfoundation/algokit-utils-py"),
    ("url", "ftp://example.com/pyproject.toml"),
    ("url", "//example.com/pyproject.toml"),
    ("url", "https:///pyproject.toml"),
    ("url", "https://"),
    ("url", "http:/example.com/pyproject.toml"),
    ("url", "https://exa mple.com/pyproject.toml"),
    ("url", "https://-bad.example/pyproject.toml"),
    ("empty", ""),
    ("empty", "   "),
]

URL_MESSAGE = "must be an absolute http(s) URL with a host"
EMPTY_MESSAGE = "must be a non-empty string"


def main():
    print(f"using {csv_to_json.__file__}")

    # --- accepted values -------------------------------------------------
    check("blank cell (None) is valid", errors_for(None) == [], str(errors_for(None)))
    check("absent key is valid", errors_for(_MISSING) == [], str(errors_for(_MISSING)))
    check(
        "non-sdks rows without the key are ignored",
        csv_to_json.validate_runtime_requirements(
            [{"slug": "some-wallet"}, "not-a-dict"], context="test"
        ) == [],
    )
    both = {
        "python": {"constraint": "^3.10", "syntax": "poetry", "source": VALID_PY_SOURCE},
        "node": {"constraint": ">=22.0", "syntax": "node-semver", "source": VALID_NODE_SOURCE},
    }
    check("python(poetry) + node(node-semver) accepted", errors_for(both) == [], str(errors_for(both)))
    check(
        "python(pep440) accepted",
        errors_for({"python": {"constraint": ">=3.10", "syntax": "pep440", "source": VALID_PY_SOURCE}}) == [],
    )
    check(
        "only one runtime declared is accepted",
        errors_for({"node": {"constraint": ">=22.0", "syntax": "node-semver", "source": VALID_NODE_SOURCE}}) == [],
    )

    # --- rejected values -------------------------------------------------
    errs = errors_for({})
    check("empty object rejected as a placeholder", len(errs) == 1 and "empty object" in errs[0], str(errs))

    errs = errors_for("python ^3.10")
    check("non-object value rejected", len(errs) == 1 and "must be a JSON object or null" in errs[0], str(errs))

    errs = errors_for({"python": {"constraint": "^3.10", "syntax": "semver", "source": VALID_PY_SOURCE}})
    check(
        "python syntax outside the enum rejected",
        len(errs) == 1 and "syntax must be one of" in errs[0],
        str(errs),
    )

    errs = errors_for({"node": {"constraint": ">=22.0", "syntax": "pep440", "source": VALID_NODE_SOURCE}})
    check(
        "node rejects python-only syntax",
        len(errs) == 1 and "syntax must be one of" in errs[0],
        str(errs),
    )

    errs = errors_for({"rust": {"constraint": ">=1.70", "syntax": "cargo", "source": VALID_PY_SOURCE}})
    check(
        "unknown runtime key rejected",
        len(errs) == 1 and "unknown runtime key" in errs[0],
        str(errs),
    )

    errs = errors_for({"python": {"constraint": "^3.10", "syntax": "poetry"}})
    check(
        "missing source rejected",
        len(errs) == 1 and "source must be a non-empty string" in errs[0],
        str(errs),
    )

    errs = errors_for({"python": {"constraint": "   ", "syntax": "poetry", "source": VALID_PY_SOURCE}})
    check(
        "blank constraint rejected",
        len(errs) == 1 and "constraint must be a non-empty string" in errs[0],
        str(errs),
    )

    errs = errors_for({"python": "^3.10"})
    check("non-object runtime entry rejected", len(errs) == 1 and "must be an object" in errs[0], str(errs))

    errs = errors_for({"python": {"constraint": "^3.10", "syntax": "semver"}, "rust": {}})
    check("multiple violations all reported", len(errs) == 3, f"{len(errs)} errors: {errs}")

    # --- the source URL rule ---------------------------------------------
    # A release-specific official declaration is a URL, not just any non-empty string:
    # `minLength` alone accepted source="not-a-url" (USS-Supervisor, 2026-09-16).
    for expected, value in SOURCE_URL_TABLE:
        errs = errors_for({"python": {"constraint": "^3.10", "syntax": "poetry", "source": value}})
        want = {"ok": None, "url": URL_MESSAGE, "empty": EMPTY_MESSAGE}[expected]
        if want is None:
            check(f"source accepted: {value[:48]!r}", errs == [], str(errs))
        else:
            check(
                f"source rejected [{expected}]: {value[:48]!r}",
                len(errs) == 1 and want in errs[0],
                str(errs),
            )

    # --- schema.json and this module must agree ---------------------------
    # The pattern is duplicated by necessity (a JSON Schema cannot call this function),
    # so pin it: identical strings, and identical verdicts on every value above.
    schema, schema_path = load_schema()
    print(f"using {schema_path}")
    source_props = {
        rt: schema["$defs"]["sdks"]["properties"]["runtimeRequirements"]["properties"][rt]
        ["properties"]["source"]
        for rt in ("python", "node")
    }
    check(
        "both source properties carry a pattern",
        all("pattern" in p for p in source_props.values()),
        str({rt: list(p) for rt, p in source_props.items()}),
    )
    check(
        "both source properties keep minLength 1",
        all(p.get("minLength") == 1 for p in source_props.values()),
    )
    for rt, prop in source_props.items():
        check(
            f"schema pattern for {rt} is identical to SOURCE_URL_PATTERN",
            prop.get("pattern") == csv_to_json.SOURCE_URL_PATTERN,
            f"schema={prop.get('pattern')!r} module={csv_to_json.SOURCE_URL_PATTERN!r}",
        )
        mismatched = [
            (expected, value) for expected, value in SOURCE_URL_TABLE
            if bool(re.search(prop["pattern"], value)) != csv_to_json.is_source_url(value)
        ]
        check(
            f"schema {rt} pattern and is_source_url() agree on all {len(SOURCE_URL_TABLE)} values",
            mismatched == [], str(mismatched),
        )

    # --- wiring ----------------------------------------------------------
    # A unit test that calls the function directly cannot notice a call being removed
    # from main(). Two call sites are required and each is asserted separately: the
    # network one sees the values a listing overrides a canonical offer with, the
    # canonical one sees offers that no listing references at all.
    flat = re.sub(r"\s+", " ", inspect.getsource(csv_to_json.main))
    check(
        "main() validates the network result",
        'validate_runtime_requirements( result.get("sdks", []), context=f"network' in flat,
    )
    check(
        "main() validates the canonical offers",
        'validate_runtime_requirements( offers_by_category.get("sdks", []), '
        'context="references/offers"' in flat,
    )
    check(
        "both call sites exit non-zero on errors",
        "runtime_req_errors" in flat and "offer_runtime_req_errors" in flat
        and flat.count("exit(1)") >= 2,
        flat[:0] or "one of the two error handlers is missing",
    )

    if FAILURES:
        print(f"\n{len(FAILURES)} check(s) failed: {', '.join(FAILURES)}")
        raise SystemExit(1)
    print("\nAll runtimeRequirements regression checks passed.")


if __name__ == "__main__":
    main()
