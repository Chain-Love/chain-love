"""Unit tests for the DBIP #3724 requestLimits change (PR #3738).

Run from the repository root:  python3 tools/tests/test_request_limits.py

The three files this PR touches are checked both on their own and against each
other, because a schema, a column description and a converter rule that drift
apart is exactly the failure mode the CI is supposed to catch:

  tools/schema.json    - the optional object array and its two enums
  meta/columns.json    - the contributor-facing description of the column
  tools/csv_to_json.py - validate_request_limits() and its wiring into main()
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

from jsonschema import Draft202012Validator

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE.parent))

import csv_to_json  # noqa: E402  (importable only after the path tweak)

COLUMN = "requestLimits"
METRICS = ("batchRequests", "blockSpan")
TRANSPORTS = ("http", "websocket")
KEYS = {"method", "transport", "metric", "maximum", "sourceUrl"}

SOURCE = "https://www.alchemy.com/docs/reference/batch-requests"
NOT_EMPTY = "sourceUrl must be a non-empty string"
ABSOLUTE = "sourceUrl must be an absolute http(s) URL with a host"

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


def entry(**overrides):
    base = {"method": "*", "transport": "http", "metric": "batchRequests",
            "maximum": 1000, "sourceUrl": SOURCE}
    base.update(overrides)
    return base


def row(value, slug="demo-rpc"):
    """A row carrying every key $defs/apis marks as required, plus the column."""
    full = {
        "slug": slug,
        "provider": "Acme",
        "planType": "Tiered",
        "apiType": "RPC",
        "chain": "ethereum",
        "address": None,
        "accessPrice": "$29/mo",
        "queryPrice": "$0",
        "uptimeSla": "99.9%",
        "bandwidthSla": None,
        "blocksBehindSla": None,
        "starred": False,
        "trial": False,
        "availableApis": ["eth"],
        "limitations": ["100 req/s"],
        "securityImprovements": ["Privacy Protected Relays"],
        "monitoringAndAnalytics": ["Real-time monitoring"],
        "regions": ["Global"],
        "actionButtons": ["[Docs](https://example.com/docs)"],
        "supportSla": None,
        "technology": "EVM JSON-RPC",
        "additionalFeatures": ["Premium Service"],
        "historicalData": "Archive",
        "tag": ["RPC"],
    }
    full[COLUMN] = value
    return full


def errors(value):
    return csv_to_json.validate_request_limits([row(value)], context="unit")


def has(value, needle):
    return any(needle in e for e in errors(value))


# ---------------------------------------------------------------------------
print("schema.json: the column is declared on $defs/apis and nowhere else")
schema = json.loads((REPO / "tools" / "schema.json").read_bytes().decode("utf-8"))
apis = schema["$defs"]["apis"]
check("requestLimits is an apis property", COLUMN in apis["properties"])
prop = apis["properties"][COLUMN]
check("type is [array, null]", prop["type"] == ["array", "null"])
check("items are objects", prop["items"]["type"] == "object")
check("items close additionalProperties", prop["items"]["additionalProperties"] is False)
check("items require all five keys", set(prop["items"]["required"]) == KEYS)
check("items declare all five keys", set(prop["items"]["properties"]) == KEYS)
check("transport enum", prop["items"]["properties"]["transport"].get("enum") == list(TRANSPORTS))
check("metric enum", prop["items"]["properties"]["metric"].get("enum") == list(METRICS))
check("maximum is a positive integer",
      prop["items"]["properties"]["maximum"] == {"type": "integer", "minimum": 1})
check("method is a non-empty string",
      prop["items"]["properties"]["method"] == {"type": "string", "minLength": 1})
check("sourceUrl is a non-empty string carrying the URL pattern",
      prop["items"]["properties"]["sourceUrl"]["type"] == "string"
      and prop["items"]["properties"]["sourceUrl"]["minLength"] == 1
      and isinstance(prop["items"]["properties"]["sourceUrl"].get("pattern"), str))
other_defs = [n for n, d in schema["$defs"].items()
              if n != "apis" and COLUMN in d.get("properties", {})]
check("no other category declares the column", other_defs == [])
check("apis still closes additionalProperties", apis.get("additionalProperties") is False)

print("schema.json: a valid array and an invalid one behave as declared")
validator = Draft202012Validator(schema).evolve(schema=apis)
check("a well-formed entry validates", validator.is_valid(row([entry()])))
check("an unknown transport is rejected",
      not validator.is_valid(row([entry(transport="grpc")])))
check("an unknown metric is rejected",
      not validator.is_valid(row([entry(metric="rateLimitPerSecond")])))
check("maximum 0 is rejected", not validator.is_valid(row([entry(maximum=0)])))
check("a missing sourceUrl is rejected",
      not validator.is_valid(row([{k: v for k, v in entry().items() if k != "sourceUrl"}])))
check("an extra key is rejected",
      not validator.is_valid(row([entry(note="paid plans only")])))
check("blank stays valid", validator.is_valid(row(None)))

# ---------------------------------------------------------------------------
print("meta/columns.json: the column is described for contributors")
columns = json.loads((REPO / "meta" / "columns.json").read_bytes().decode("utf-8"))
check("requestLimits is described", COLUMN in columns)
meta = columns[COLUMN]
check("key matches the column name", meta["key"] == COLUMN)
check("label is human readable", meta["label"] == "Request limits")
check("description states that blank means unverified",
      "Blank means not yet verified" in meta["description"])
check("description mentions the source requirement", "source" in meta["description"].lower())
check("description names both metrics",
      all(m in meta["description"] for m in METRICS))
check("cellType is arrayPopover", meta["cellType"] == "arrayPopover")
check("group is capabilities", meta["group"] == "capabilities")
check("sorting is arrayLength", meta["sorting"] == "arrayLength")
check("every other column is untouched by this PR",
      len(columns) > 20 and all("requestLimits" not in k for k in columns if k != COLUMN))

# ---------------------------------------------------------------------------
print("csv_to_json.py: the vocabulary is shared with the schema")
check("REQUEST_LIMITS_COLUMN", csv_to_json.REQUEST_LIMITS_COLUMN == COLUMN)
check("REQUEST_LIMIT_METRICS", csv_to_json.REQUEST_LIMIT_METRICS == METRICS)
check("REQUEST_LIMIT_TRANSPORTS", csv_to_json.REQUEST_LIMIT_TRANSPORTS == TRANSPORTS)
check("schema and converter agree on metrics",
      list(csv_to_json.REQUEST_LIMIT_METRICS) == prop["items"]["properties"]["metric"].get("enum"))
check("schema and converter agree on transports",
      list(csv_to_json.REQUEST_LIMIT_TRANSPORTS)
      == prop["items"]["properties"]["transport"].get("enum"))

print("csv_to_json.py: validate_request_limits() accepts what it should")
check("blank is accepted (unverified)", errors(None) == [])
check("a blank CSV cell never reaches the validator as ''",
      csv_to_json.normalize({"apis": [{"requestLimits": ""}]})
      == ({"apis": [{"requestLimits": None}]}, []))
check("an empty array is accepted", errors([]) == [])
check("one well-formed entry is accepted", errors([entry()]) == [])
check("two entries with different metrics are accepted",
      errors([entry(), entry(metric="blockSpan", maximum=10000)]) == [])
check("the same metric on two transports is accepted",
      errors([entry(), entry(transport="websocket", maximum=20)]) == [])
check("the same metric on two methods is accepted",
      errors([entry(), entry(method="eth_getLogs", maximum=20)]) == [])
check("a large maximum is accepted", errors([entry(maximum=2_000_000_000)]) == [])
check("an https source is accepted", errors([entry(sourceUrl=SOURCE)]) == [])
check("a row without the column is accepted",
      csv_to_json.validate_request_limits([{"slug": "x"}], context="unit") == [])

print("csv_to_json.py: each rule of DBIP #3724 rejects on its own")
check("not an array", has(entry(), "must be a JSON array"))
check("entry is not an object", has(["http"], "must be an object"))
check("missing key", has([{k: v for k, v in entry().items() if k != "sourceUrl"}],
                         "keys mismatch"))
check("extra key", has([entry(note="x")], "keys mismatch"))
check("empty method", has([entry(method="")], "method must be a non-empty string"))
check("blank method", has([entry(method="   ")], "method must be a non-empty string"))
check("non-string method", has([entry(method=7)], "method must be a non-empty string"))
check("unknown transport", has([entry(transport="grpc")], "transport must be one of"))
check("uppercase transport", has([entry(transport="HTTP")], "transport must be one of"))
check("unknown metric", has([entry(metric="rateLimitPerSecond")], "metric must be one of"))
check("uppercase metric", has([entry(metric="BatchRequests")], "metric must be one of"))
check("maximum 0 (no sentinel)", has([entry(maximum=0)], "maximum must be a positive integer"))
check("negative maximum", has([entry(maximum=-5)], "maximum must be a positive integer"))
check("boolean maximum", has([entry(maximum=True)], "maximum must be a positive integer"))
check("string maximum", has([entry(maximum="1000")], "maximum must be a positive integer"))
check("float maximum", has([entry(maximum=1.5)], "maximum must be a positive integer"))
check("source without a scheme",
      has([entry(sourceUrl="www.example.com/docs")], ABSOLUTE))
check("non-http scheme", has([entry(sourceUrl="ftp://example.com")], ABSOLUTE))
check("a bare scheme is not a URL", has([entry(sourceUrl="https://")], ABSOLUTE))
check("a scheme with no host is not a URL",
      has([entry(sourceUrl="https:///batch-requests")], ABSOLUTE))
check("a malformed host is not a URL",
      has([entry(sourceUrl="https://-bad.example/limits")], ABSOLUTE))
check("empty source is the blankness rule, not the URL rule",
      has([entry(sourceUrl="")], NOT_EMPTY))
check("blank source is the blankness rule",
      has([entry(sourceUrl="   ")], NOT_EMPTY))
check("non-string source is the blankness rule, not the URL rule",
      has([entry(sourceUrl=1234)], NOT_EMPTY))
check("the two source messages are distinct, so a mutation cannot hide",
      ABSOLUTE not in NOT_EMPTY and NOT_EMPTY not in ABSOLUTE)
check("duplicate (method, transport, metric)",
      has([entry(), entry(maximum=99)], "duplicates (method, transport, metric)"))
check("the offending row is named", has([entry(transport="grpc")], "apis 'demo-rpc'"))
check("the offending position is named", has([entry(transport="grpc")], "requestLimits[0]"))
check("a later bad entry is still reported",
      has([entry(), entry(metric="nope")], "requestLimits[1]"))
check("http:// is allowed", errors([entry(sourceUrl="http://example.com/docs")]) == [])

# Nested containers are not scalars, and they used to be the one input that turned a
# validation error into a converter crash: the field's own rule reported the value and
# then the same value was handed to the (method, transport, metric) uniqueness set,
# which raised `TypeError: unhashable type: 'list'` before the message was printed.
# csv_to_json.py runs before validate.py, so the schema layer cannot rescue that order.
# Each case below therefore asserts the field's own message *and* that the entry
# produced exactly one error -- a crash cannot satisfy either, and a stray extra error
# would mean the entry was also fed to some other rule.
print("csv_to_json.py: a nested array or object is a validation error, not a crash")
CONTAINER_FIELDS = (
    ("method", "method must be a non-empty string"),
    ("transport", "transport must be one of"),
    ("metric", "metric must be one of"),
    ("maximum", "maximum must be a positive integer"),
    ("sourceUrl", NOT_EMPTY),
)
for kind, bad in (("array", []), ("object", {})):
    for field, message in CONTAINER_FIELDS:
        got = errors([entry(**{field: bad})])
        check(f"{field} as a nested {kind} takes its own rule",
              any(message in e for e in got))
        check(f"{field} as a nested {kind} yields one error and no traceback",
              len(got) == 1)
check("a malformed entry does not stop a later duplicate being reported",
      has([entry(transport=[]), entry(), entry(maximum=99)],
          "duplicates (method, transport, metric)"))
check("two entries carrying the same nested container are each reported, never keyed",
      len(errors([entry(metric=[]), entry(metric=[])])) == 2)
check("the uniqueness rule still fires on a well-formed triple",
      has([entry(), entry(maximum=99)], "duplicates (method, transport, metric)"))

# ---------------------------------------------------------------------------
print("csv_to_json.py: the validator is wired into both passes of main()")
src = (REPO / "tools" / "csv_to_json.py").read_bytes().decode("utf-8")
check("canonical offers are validated",
      "canonical_request_limit_errors = validate_request_limits(" in src)
check("network listings are validated",
      "request_limit_errors = validate_request_limits(" in src)
check("the canonical pass exits on error",
      "if canonical_request_limit_errors:" in src)
check("the network pass exits on error", "if request_limit_errors:" in src)


# ---------------------------------------------------------------------------
print("sourceUrl: one verdict table, replayed against both layers")
# The regex is declared twice on purpose -- once in csv_to_json.py and once as the
# `pattern` of the sourceUrl property in tools/schema.json -- because either layer can be
# the one that sees a value first. A table is therefore only trustworthy if BOTH layers
# agree on it, so every verdict below is replayed against the python rule and against
# `re.search(schema pattern, value)`.
SOURCE_URL_TABLE = [
    ("ok", "https://www.alchemy.com/docs/reference/batch-requests"),
    ("ok", "http://example.com/docs"),
    ("ok", "HTTPS://EXAMPLE.COM/docs"),
    ("ok", "https://example.com"),
    ("ok", "https://example.com:8443/x?a=b#c"),
    ("ok", "https://192.168.1.1/x"),
    ("ok", "https://a.b-c.d/x"),
    ("url", "https://"),
    ("url", "https:///batch-requests"),
    ("url", "https://-bad.example/limits"),
    ("url", "https://exa mple.com/limits"),
    ("url", "https:// .example.com/limits"),
    ("url", "http:/example.com/x"),
    ("url", "https://#frag"),
    ("url", "https://?q=1"),
    ("url", "//example.com/x"),
    ("url", "www.example.com/docs"),
    ("url", "ftp://example.com/x"),
    ("url", "not-a-url"),
    ("empty", ""),
]

pattern = prop["items"]["properties"]["sourceUrl"]["pattern"]
check("both layers carry the same regex string",
      pattern == csv_to_json.SOURCE_URL_PATTERN)
check("the blankness rule runs first for the empty value",
      has([entry(sourceUrl="")], NOT_EMPTY))
for expected, value in SOURCE_URL_TABLE:
    in_python = csv_to_json.is_source_url(value)
    in_schema = bool(re.search(pattern, value))
    if expected == "ok":
        check(f"accepted by both layers: {value[:44]!r}", in_python and in_schema)
    elif expected == "url":
        check(f"rejected as a URL by both layers: {value[:44]!r}",
              not in_python and not in_schema)
    else:
        check(f"empty is refused by the URL rule: {value!r}", not in_python and not in_schema)

mismatched = [(e, v) for e, v in SOURCE_URL_TABLE
              if bool(re.search(pattern, v)) != csv_to_json.is_source_url(v)]
check("the two layers agree on every value in the table", mismatched == [])

print("fixtures: each canonical negative really violates the sourceUrl rule")
import csv as _csv  # noqa: E402
import io as _io  # noqa: E402

FIXDIR = HERE / "fixtures" / "request-limits"


def fixture_source(name, slug="filecoin-logs-rpc"):
    """The sourceUrl the named fixture carries on `slug` -- the one cell it changed."""
    raw = (FIXDIR / name).read_bytes().decode("utf-8")
    rows = [r for r in _csv.DictReader(_io.StringIO(raw)) if r["slug"] == slug]
    assert len(rows) == 1, f"{name}: {len(rows)} rows named {slug}"
    cell = (rows[0]["requestLimits"] or "").strip()
    assert cell, f"{name}: {slug} has no requestLimits cell"
    return json.loads(cell)[0]["sourceUrl"]


for name, value in (
    ("offers.apis.negative-source-bare-scheme.csv", "https://"),
    ("offers.apis.negative-source-no-host.csv", "https:///batch-requests"),
    ("offers.apis.negative-source-bad-host.csv", "https://-bad.example/limits"),
    ("offers.apis.negative-bad-source-url.csv", "www.example.com/docs"),
):
    got = fixture_source(name)
    check(f"{name} carries the rejected value", got == value)
    check(f"{name} is rejected by both layers",
          not csv_to_json.is_source_url(got) and not re.search(pattern, got))

positive = (FIXDIR / "offers.apis.csv").read_bytes().decode("utf-8")
positive_values = [e["sourceUrl"]
                   for r in _csv.DictReader(_io.StringIO(positive))
                   for e in (json.loads(r["requestLimits"]) if (r["requestLimits"] or "").strip() else [])]
check("every value in the positive fixture still passes",
      positive_values and all(csv_to_json.is_source_url(v) for v in positive_values))
check("the positive fixture has more than one distinct source", len(set(positive_values)) > 1)

# ---------------------------------------------------------------------------
print()
print(f"{CHECKED} checks, {len(FAILURES)} failures")
if FAILURES:
    for f in FAILURES:
        print(f"  - {f}")
    sys.exit(1)
print("OK")
