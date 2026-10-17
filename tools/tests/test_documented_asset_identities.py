"""Regression tests for the documentedAssetIdentities column (DBIP #4514).

The column lets a bridge listing record which specific token contract an offer
handles on a network, as a CAIP-19 asset id backed by a provider source URL.
The tests pin each acceptance criterion from the issue, the wiring that makes
the check fail the build, and the end-to-end guarantees:

  - a valid record survives into the generated JSON (override and inherit);
  - a bare ticker fails the build with network/category/slug context;
  - existing listings without the column keep producing identical JSON.

The benchmark section walks the real bridges listings staged in this tree (in
CI, main's data) and asserts the validator reports zero errors against every
row -- the issue's criterion 5 backward-compatibility proof at scale. At
upstream main 8903f598b9 the four pilot networks hold 207 rows (Base 53,
Ethereum 54, Arbitrum 63, Avalanche 37) and none of them, nor the 62 canonical
bridge offers, carries the column.

Criterion 2 (asset chainId must match the row's network) is exercised through
an explicit registry argument: the repository carries no network -> chainId
mapping today, so csv_to_json passes None and the check stays dormant rather
than inventing chain IDs.

Run: python3 tools/tests/test_documented_asset_identities.py
"""
from __future__ import annotations

import csv
import inspect as _inspect
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import csv_to_json as tool  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[2]
FIXTURES = REPO / "tools" / "tests" / "fixtures" / "documented-asset-identities"

USDC_NATIVE = "eip155:8453/erc20:0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
USDC_NATIVE_LOWER = "eip155:8453/erc20:0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"
USDBC_BRIDGED = "eip155:8453/erc20:0xd9aAEc86B65D86f6A7B5B1b0c42FFA531710b6CA"
# A format-only fixture for chain 1: the address is deliberately synthetic, the
# tests below care about the CAIP-19 shape, not about which token it is.
CHAIN1_TOKEN = "eip155:1/erc20:0x0000000000000000000000000000000000000001"

ERROR_PREFIX = "Invalid documentedAssetIdentities for network"

FAILURES: list[str] = []
CHECKS = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if condition:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}")
        if detail:
            print(f"       {detail}")
        FAILURES.append(label)


def record(asset_id, **extra):
    rec = {"assetId": asset_id, "sourceUrl": "https://docs.example.com/assets"}
    rec.update(extra)
    return rec


def row(slug="demo-row", identities=None, chain="mainnet"):
    r = {"slug": slug}
    if chain is not None:
        r["chain"] = chain
    if identities is not None:
        r["documentedAssetIdentities"] = identities
    return r


def errors_for(row_dict, network="base", category="bridges", registry=None):
    return tool.validate_documented_asset_identities(
        [row_dict], network_name=network, category=category, network_chain_ids=registry
    )


# ─────────────────────────────────────────────────────────────────────────────
# [CAIP-19 parsers]
# ─────────────────────────────────────────────────────────────────────────────
print("\n[parse_caip19_asset_id: the four-component structural split]")

check(
    "a full asset id splits into four components",
    tool.parse_caip19_asset_id(USDC_NATIVE)
    == ("eip155", "8453", "erc20", "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"),
    str(tool.parse_caip19_asset_id(USDC_NATIVE)),
)
check("a bare ticker is not an asset id", tool.parse_caip19_asset_id("USDC") is None)
check("a chain id without an asset part is rejected", tool.parse_caip19_asset_id("eip155:8453") is None)
check("a missing slash is rejected", tool.parse_caip19_asset_id("eip155:8453erc20:0x00") is None)
check("an empty component is rejected", tool.parse_caip19_asset_id("eip155:/erc20:0x00") is None)
check("a second slash is rejected", tool.parse_caip19_asset_id("eip155:8453/erc20:0x00/extra") is None)
check("a non-string is rejected", tool.parse_caip19_asset_id(42) is None)

print("\n[parse_eip155_erc20_asset_id: the exact EVM ERC-20 profile]")

check(
    "a checksummed Base USDC id parses",
    tool.parse_eip155_erc20_asset_id(USDC_NATIVE) == ("8453", "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"),
)
check("a bare ticker does not parse", tool.parse_eip155_erc20_asset_id("USDC") is None)
check("a short address does not parse", tool.parse_eip155_erc20_asset_id("eip155:8453/erc20:0x1234") is None)
check("a 41-hex address does not parse", tool.parse_eip155_erc20_asset_id("eip155:8453/erc20:0x" + "a" * 41) is None)
check("a non-hex address does not parse", tool.parse_eip155_erc20_asset_id("eip155:8453/erc20:0x" + "z" * 40) is None)
check("a non-numeric chain reference does not parse", tool.parse_eip155_erc20_asset_id("eip155:base/erc20:0x" + "a" * 40) is None)
check("a non-erc20 asset namespace does not parse", tool.parse_eip155_erc20_asset_id("eip155:8453/slip44:60") is None)
check("a missing 0x prefix does not parse", tool.parse_eip155_erc20_asset_id("eip155:8453/erc20:" + "a" * 40) is None)


# ─────────────────────────────────────────────────────────────────────────────
# [criterion 1: exact eip155 ERC-20 asset ids, tickers rejected]
# ─────────────────────────────────────────────────────────────────────────────
print("\n[criterion 1: assetId must be an exact CAIP-19 asset type]")

check(
    "a valid record produces no errors",
    errors_for(row(identities=[record(USDC_NATIVE)])) == [],
    str(errors_for(row(identities=[record(USDC_NATIVE)]))),
)
errs = errors_for(row(identities=[record("USDC")]))
check("a bare ticker is rejected", len(errs) == 1 and "not a CAIP-19 asset id" in errs[0], str(errs))
check(
    "the ticker error explains the expected shape",
    any("a ticker such as 'USDC' alone is not an asset identity" in e for e in errs),
    str(errs),
)
errs = errors_for(row(identities=[record("eip155:8453/erc20:0x1234")]))
check("a truncated address is rejected", len(errs) == 1 and "not an exact eip155 ERC-20" in errs[0], str(errs))
errs = errors_for(row(identities=[record("eip155:base/erc20:0x" + "a" * 40)]))
check("a non-numeric chain reference is rejected", len(errs) == 1 and "must be numeric" in errs[0], str(errs))
errs = errors_for(row(identities=[{"sourceUrl": "https://docs.example.com/x"}]))
check("a record without assetId is rejected", len(errs) == 1 and "missing the required assetId" in errs[0], str(errs))
check(
    "the error names network, category and slug",
    errs and errs[0].startswith("base/bridges/demo-row: documentedAssetIdentities[0]"),
    str(errs),
)

# ─────────────────────────────────────────────────────────────────────────────
# [criterion 3: an https provider source URL is required]
# ─────────────────────────────────────────────────────────────────────────────
print("\n[criterion 3: sourceUrl is required and must be https]")

errs = errors_for(row(identities=[{"assetId": USDC_NATIVE}]))
check("a record without sourceUrl is rejected", len(errs) == 1 and "missing the required sourceUrl" in errs[0], str(errs))
errs = errors_for(row(identities=[record(USDC_NATIVE, sourceUrl="http://docs.example.com/x")]))
check("an http sourceUrl is rejected", len(errs) == 1 and "must be an https link" in errs[0], str(errs))
errs = errors_for(row(identities=[record(USDC_NATIVE, sourceUrl="docs.example.com/x")]))
check("a scheme-less sourceUrl is rejected", len(errs) == 1 and "must be an https link" in errs[0], str(errs))
check(
    "an https sourceUrl is accepted",
    errors_for(row(identities=[record(USDC_NATIVE, sourceUrl="https://docs.across.to/guides/migration/cctp")])) == [],
)

# ─────────────────────────────────────────────────────────────────────────────
# [criterion 4: duplicates and the optional enums]
# ─────────────────────────────────────────────────────────────────────────────
print("\n[criterion 4: duplicate normalized assetIds and the optional enums]")

errs = errors_for(row(identities=[record(USDC_NATIVE), record(USDC_NATIVE_LOWER)]))
check("a case-insensitive duplicate is rejected", len(errs) == 1 and "duplicates" in errs[0], str(errs))
check(
    "the duplicate error preserves both supplied spellings",
    errs and USDC_NATIVE in errs[0] and USDC_NATIVE_LOWER in errs[0],
    str(errs),
)
errs = errors_for(row(identities=[record("eip155:08453/erc20:0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"), record(USDC_NATIVE)]))
check("a leading-zero chainId duplicates its canonical form", len(errs) == 1 and "duplicates" in errs[0], str(errs))
check(
    "the same address on another chain is not a duplicate",
    errors_for(row(identities=[record(USDBC_BRIDGED), record(CHAIN1_TOKEN)])) == [],
    str(errors_for(row(identities=[record(USDBC_BRIDGED), record(CHAIN1_TOKEN)]))),
)
errs = errors_for(row(identities=[record(USDC_NATIVE, representation="native")]))
check("an unknown representation is rejected", len(errs) == 1 and "representation" in errs[0], str(errs))
errs = errors_for(row(identities=[record(USDC_NATIVE, usage="from")]))
check("an unknown usage is rejected", len(errs) == 1 and "usage" in errs[0], str(errs))
check(
    "every documented representation is accepted",
    all(errors_for(row(identities=[record(USDC_NATIVE, representation=r)])) == []
        for r in tool.ASSET_REPRESENTATIONS),
)
check(
    "every documented usage is accepted",
    all(errors_for(row(identities=[record(USDC_NATIVE, usage=u)])) == []
        for u in tool.ASSET_USAGES),
)
check(
    "omitted representation and usage are accepted",
    errors_for(row(identities=[record(USDC_NATIVE)])) == [],
)

# ─────────────────────────────────────────────────────────────────────────────
# [checkedAt: optional YYYY-MM-DD]
# ─────────────────────────────────────────────────────────────────────────────
print("\n[checkedAt: an optional real calendar date]")

check(
    "a real date is accepted",
    errors_for(row(identities=[record(USDC_NATIVE, checkedAt="2026-10-17")])) == [],
)
errs = errors_for(row(identities=[record(USDC_NATIVE, checkedAt="2026-13-45")]))
check("an impossible date is rejected", len(errs) == 1 and "not a real calendar date" in errs[0], str(errs))
errs = errors_for(row(identities=[record(USDC_NATIVE, checkedAt="2026-02-30")]))
check("Feb 30 is rejected", len(errs) == 1 and "not a real calendar date" in errs[0], str(errs))
errs = errors_for(row(identities=[record(USDC_NATIVE, checkedAt="17/10/2026")]))
check("a wrong format is rejected", len(errs) == 1 and "YYYY-MM-DD" in errs[0], str(errs))

# ─────────────────────────────────────────────────────────────────────────────
# [criterion 5: missing, blank or NULL columns are skipped]
# ─────────────────────────────────────────────────────────────────────────────
print("\n[criterion 5: rows without the column are untouched]")

check("a row without the column is skipped", errors_for(row(identities=None)) == [])
check(
    "an explicit None value is skipped",
    errors_for({"slug": "demo-row", "chain": "mainnet", "documentedAssetIdentities": None}) == [],
)
errs = errors_for({"slug": "x", "documentedAssetIdentities": "USDC"})
check("a non-array value is an error, not a skip", len(errs) == 1 and "must be a JSON array" in errs[0], str(errs))
errs = errors_for({"slug": "x", "documentedAssetIdentities": ["not-an-object"]})
check("a non-object record is an error", len(errs) == 1 and "must be a JSON object" in errs[0], str(errs))
check(
    "rows in unrelated categories are untouched",
    tool.validate_documented_asset_identities(
        [{"slug": "x", "assetTypes": ["USDC"]}], "base", "apis"
    ) == [],
)

# ─────────────────────────────────────────────────────────────────────────────
# [criterion 2: chainId vs network, through an explicit registry]
# ─────────────────────────────────────────────────────────────────────────────
print("\n[criterion 2: the registry path (dormant without a registry)]")

REGISTRY = {"base": {"mainnet": "8453", "testnet": "84532"}, "ethereum": {"mainnet": "1"}}
check(
    "a matching chainId passes",
    errors_for(row(identities=[record(USDC_NATIVE)]), registry=REGISTRY) == [],
    str(errors_for(row(identities=[record(USDC_NATIVE)]), registry=REGISTRY)),
)
errs = errors_for(row(identities=[record(USDC_NATIVE)]), network="ethereum", registry=REGISTRY)
check(
    "a Base mainnet asset id in an Ethereum row is rejected",
    len(errs) == 1 and "chainId 8453 does not match network 'ethereum'" in errs[0],
    str(errs),
)
check(
    "an Ethereum asset id in an Ethereum row passes",
    errors_for(row(identities=[record(CHAIN1_TOKEN)]), network="ethereum", registry=REGISTRY) == [],
)
errs = errors_for(row(identities=[record(USDC_NATIVE)], chain="testnet"), registry=REGISTRY)
check(
    "a mainnet asset id in a testnet row is rejected",
    len(errs) == 1 and "testnet expects 84532" in errs[0],
    str(errs),
)
check(
    "an environment missing from the registry is not enforced",
    errors_for(row(identities=[record(USDC_NATIVE)], chain="sepolia"), registry=REGISTRY) == [],
)
check(
    "without a registry the criterion stays dormant",
    errors_for(row(identities=[record(USDC_NATIVE)]), network="ethereum") == [],
)


# ─────────────────────────────────────────────────────────────────────────────
# [wiring: resolve_offers runs the check on merged rows and fails the build]
# ─────────────────────────────────────────────────────────────────────────────
print("\n[wiring: the validator is called from resolve_offers]")

resolve_src = _inspect.getsource(tool.resolve_offers)
check(
    "resolve_offers calls validate_documented_asset_identities",
    "validate_documented_asset_identities(" in resolve_src,
)
check(
    "the call passes network and category context",
    "network_name=network_name" in resolve_src and "category=category" in resolve_src,
)
check(
    "errors raise instead of being printed",
    "raise ValueError" in resolve_src,
)
check(
    "the raise mentions the column name",
    "Invalid documentedAssetIdentities for network" in resolve_src,
)
call_site = resolve_src[
    resolve_src.index("validate_documented_asset_identities(") :
].split(")")[0]
check(
    "the wiring passes no registry, so criterion 2 stays dormant",
    "network_chain_ids" not in call_site,
    call_site,
)


def stage_e2e(bad: bool) -> pathlib.Path:
    """Assemble a minimal generator workspace in a temp directory.

    git does not track empty directories, so listings/all-networks is created
    here rather than expected to survive the checkout. tools/schema.json is
    copied from this tree because main() reads the schema version from it.
    """
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="dai-e2e-"))
    (tmp / "listings" / "all-networks").mkdir(parents=True, exist_ok=True)
    network_dir = tmp / "listings" / "specific-networks" / "demo"
    network_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(FIXTURES / "e2e-network" / "references", tmp / "references")
    shutil.copytree(FIXTURES / "e2e-network" / "meta", tmp / "meta")
    shutil.copyfile(REPO / "tools" / "schema.json", tmp / "schema.json")
    listing = "listings.bridges.bad.csv" if bad else "listings.bridges.csv"
    shutil.copyfile(FIXTURES / listing, network_dir / "bridges.csv")
    return tmp


# ─────────────────────────────────────────────────────────────────────────────
# [e2e: a valid tree generates JSON with the column resolved]
# ─────────────────────────────────────────────────────────────────────────────
print("\n[e2e: valid records survive into json/demo.json]")

tmp = stage_e2e(bad=False)
try:
    proc = subprocess.run(
        [sys.executable, str(REPO / "tools" / "csv_to_json.py")],
        cwd=str(tmp),
        capture_output=True,
        text=True,
        timeout=180,
    )
    check("the run exits zero", proc.returncode == 0, f"rc={proc.returncode}\n{proc.stderr[-500:]}")
    written = tmp / "json" / "demo.json"
    check("json/demo.json is written", written.exists())
    if written.exists():
        data = json.loads(written.read_text(encoding="utf-8"))
        by_slug = {w.get("slug"): w for w in data.get("bridges", [])}
        check(
            "the overriding row keeps its own issuer_native record",
            by_slug.get("demo-valid", {}).get("documentedAssetIdentities")
            == [{
                "assetId": USDC_NATIVE,
                "representation": "issuer_native",
                "usage": "both",
                "sourceUrl": "https://docs.example.com/cctp",
                "checkedAt": "2026-10-17",
            }],
            str(by_slug.get("demo-valid", {}).get("documentedAssetIdentities")),
        )
        check(
            "the blank row inherits the offer's bridged record",
            by_slug.get("demo-blank", {}).get("documentedAssetIdentities")
            == [{
                "assetId": USDBC_BRIDGED,
                "representation": "bridged",
                "sourceUrl": "https://docs.example.com/assets",
            }],
            str(by_slug.get("demo-blank", {}).get("documentedAssetIdentities")),
        )
        check(
            "the inheriting row resolves to the same offer record",
            by_slug.get("demo-inherit", {}).get("documentedAssetIdentities")
            == by_slug.get("demo-blank", {}).get("documentedAssetIdentities"),
        )
        check(
            "a plain row without an offer reference keeps its record",
            by_slug.get("demo-plain", {}).get("documentedAssetIdentities")
            == [{"assetId": USDC_NATIVE, "sourceUrl": "https://docs.example.com/assets"}],
            str(by_slug.get("demo-plain", {}).get("documentedAssetIdentities")),
        )
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# ─────────────────────────────────────────────────────────────────────────────
# [e2e: a bare ticker fails the build with context]
# ─────────────────────────────────────────────────────────────────────────────
print("\n[e2e: a ticker assetId fails the build]")

tmp = stage_e2e(bad=True)
try:
    proc = subprocess.run(
        [sys.executable, str(REPO / "tools" / "csv_to_json.py")],
        cwd=str(tmp),
        capture_output=True,
        text=True,
        timeout=180,
    )
    combined = proc.stdout + proc.stderr
    check("the run exits non-zero", proc.returncode != 0, f"rc={proc.returncode}")
    check(
        "the failure names the network, category and slug",
        "demo/bridges/demo-ticker" in combined,
        combined[-400:],
    )
    check(
        "the failure explains the ticker is not an asset id",
        "not a CAIP-19 asset id" in combined,
        combined[-400:],
    )
    check("no json is written for the failing network", not (tmp / "json" / "demo.json").exists())
finally:
    shutil.rmtree(tmp, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# [schema: the column validates against tools/schema.json]
# ─────────────────────────────────────────────────────────────────────────────
print("\n[schema: documentedAssetIdentities against tools/schema.json]")

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover - dependency is declared in tools/requirements.txt
    Draft202012Validator = None

if Draft202012Validator is None:
    print("       skipped: jsonschema not installed (tools/requirements.txt)")
else:
    schema = json.loads((REPO / "tools" / "schema.json").read_text(encoding="utf-8"))
    bridges_validator = Draft202012Validator({"$defs": schema["$defs"], "$ref": "#/$defs/bridges"})

    def bridges_row(**overrides):
        base = {
            "slug": "demo-bridge",
            "provider": "Demo Provider",
            "chain": "mainnet",
            "technology": "Lock-and-mint",
            "openSource": False,
            "support": None,
            "supportedChains": ["base"],
            "starred": False,
            "availableApis": None,
            "monitoringAndAnalytics": None,
            "additionalFeatures": None,
            "assetTypes": ["Stablecoins"],
            "txSpeedSla": None,
            "throughputSla": None,
            "price": None,
            "economicalSecurity": False,
            "economicalSecurityNote": None,
            "auditsPerformed": None,
            "decentralizationModel": None,
            "sdk": None,
            "actionButtons": None,
            "tag": None,
            "offer": None,
        }
        base.update(overrides)
        return base

    def schema_errors(row_dict):
        return [e.message for e in bridges_validator.iter_errors(row_dict)]

    good_record = {
        "assetId": USDC_NATIVE,
        "representation": "issuer_native",
        "usage": "origin",
        "sourceUrl": "https://docs.example.com/cctp",
        "checkedAt": "2026-10-17",
    }
    check(
        "a row without the column still validates",
        schema_errors(bridges_row()) == [],
        str(schema_errors(bridges_row())),
    )
    check(
        "a row with a full record validates",
        schema_errors(bridges_row(documentedAssetIdentities=[good_record])) == [],
        str(schema_errors(bridges_row(documentedAssetIdentities=[good_record]))),
    )
    check(
        "a minimal record (assetId + sourceUrl only) validates",
        schema_errors(
            bridges_row(
                documentedAssetIdentities=[
                    {"assetId": USDC_NATIVE, "sourceUrl": "https://docs.example.com/x"}
                ]
            )
        ) == [],
    )
    check(
        "a NULL column value validates",
        schema_errors(bridges_row(documentedAssetIdentities=None)) == [],
    )
    check(
        "an unknown representation fails the schema",
        any("'native' is not one of" in m for m in schema_errors(
            bridges_row(documentedAssetIdentities=[dict(good_record, representation="native")])
        )),
        str(schema_errors(bridges_row(documentedAssetIdentities=[dict(good_record, representation="native")]))),
    )
    check(
        "a record without sourceUrl fails the schema",
        schema_errors(
            bridges_row(documentedAssetIdentities=[{"assetId": USDC_NATIVE}])
        ) != [],
    )
    check(
        "a record with an unknown key fails the schema",
        schema_errors(
            bridges_row(documentedAssetIdentities=[dict(good_record, decimals=6)])
        ) != [],
    )
    check(
        "a non-array column value fails the schema",
        schema_errors(bridges_row(documentedAssetIdentities=good_record)) != [],
    )


# ─────────────────────────────────────────────────────────────────────────────
# [benchmark: the real bridges listings in this tree stay clean]
# ─────────────────────────────────────────────────────────────────────────────
print("\n[benchmark: real bridges listings produce zero validation errors]")

NETWORKS_DIR = REPO / "listings" / "specific-networks"
OFFERS_FILE = REPO / "references" / "offers" / "bridges.csv"


def read_csv_rows(path: pathlib.Path):
    with open(path, newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("slug")]


def real_row_errors():
    """Run the tool's validator over raw CSV rows of the staged bridges data.

    Rows are read straight from disk (no normalization): the column is absent
    from every real file today, which is exactly the criterion-5 case. If a
    future listing carries the column, the same walk validates it.
    """
    found = []
    row_count = 0
    if OFFERS_FILE.is_file():
        for r in read_csv_rows(OFFERS_FILE):
            row_count += 1
            found += tool.validate_documented_asset_identities(
                [r], network_name="all-networks", category="bridges"
            )
    if NETWORKS_DIR.is_dir():
        for network_dir in sorted(NETWORKS_DIR.iterdir()):
            listing = network_dir / "bridges.csv"
            if not listing.is_file():
                continue
            for r in read_csv_rows(listing):
                row_count += 1
                found += tool.validate_documented_asset_identities(
                    [r], network_name=network_dir.name, category="bridges"
                )
    return found, row_count


if NETWORKS_DIR.is_dir() or OFFERS_FILE.is_file():
    found, row_count = real_row_errors()
    check(
        "every real bridges row validates",
        not found,
        f"{len(found)} errors, first: {found[:2]}",
    )
    print(f"       real bridges rows scanned in this tree: {row_count}")

    # The generator must still succeed over the real tree with the new schema
    # and validator wired in -- the end-to-end backward-compatibility proof.
    gen = subprocess.run(
        [sys.executable, str(REPO / "tools" / "csv_to_json.py")],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=600,
    )
    check(
        "the generator exits zero over the real tree",
        gen.returncode == 0,
        f"rc={gen.returncode}\n{gen.stderr[-400:]}",
    )
    # json/ is scratch output for this run only.
    shutil.rmtree(REPO / "json", ignore_errors=True)
else:
    print("       skipped: no listings/ staged in this checkout (tools-only tree)")

print(f"\n{CHECKS - len(FAILURES)}/{CHECKS} checks passed")
if FAILURES:
    print("FAILED:")
    for f in FAILURES:
        print("  -", f)
    raise SystemExit(1)
print("All documentedAssetIdentities regression checks passed.")
