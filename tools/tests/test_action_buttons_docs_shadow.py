"""Regression tests for the actionButtons Docs-shadow advisory (DBIP #4512).

The advisory exists because actionButtons is a JSON array and resolve_offers
replaces it wholesale: a network-specific one-button override silently drops the
canonical offer's verified [Docs] link. The tests pin the four documented
conditions, the wiring that makes the advisory reach stdout, and the end-to-end
guarantee that the generated JSON is left untouched.

The benchmark section reproduces the issue's four-network scan (Algorand,
Avalanche, Filecoin, Somnia) against whatever tree the suite runs in. At upstream
main 8903f598b9 it reported 37 candidates (10/19/6/2); the count drifts as data
merges, so the test asserts agreement between the scan and the tool rather than a
frozen number.

Run: python3 tools/tests/test_action_buttons_docs_shadow.py
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
FIXTURES = REPO / "tools" / "tests" / "fixtures" / "action-buttons-docs-shadow"
E2E_ROOT = FIXTURES / "e2e-network"

BENCHMARK_NETWORKS = ("algorand", "avalanche", "filecoin", "somnia")
ADVISORY_PREFIX = "WARNING: actionButtons_docs_shadowed: "

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


def offer_row(buttons):
    return {"slug": "demo-offer", "actionButtons": buttons}


def listing_row(buttons):
    return {"slug": "demo-listing", "actionButtons": buttons}


# ─────────────────────────────────────────────────────────────────────────────
# [the label helper]
# ─────────────────────────────────────────────────────────────────────────────
print("\n[action_button_label: the [Label] of a markdown-link button]")


def test_label_helper():
    check("a plain button yields its label", tool.action_button_label("[Docs](https://x)") == "Docs")
    check("a spaced label is preserved", tool.action_button_label("[Contact Sales](https://x)") == "Contact Sales")
    check("a button without a closing bracket has no label", tool.action_button_label("[Docs") is None)
    check("a button that does not start with a bracket has no label", tool.action_button_label("Docs](https://x)") is None)
    check("a non-string button has no label", tool.action_button_label({"label": "Docs"}) is None)
    check("an empty label is empty, not None", tool.action_button_label("[](https://x)") == "")


test_label_helper()


# ─────────────────────────────────────────────────────────────────────────────
# [the four documented conditions, one case each]
# ─────────────────────────────────────────────────────────────────────────────
print("\n[condition 1: canonical [Website, Docs] and listing [Explore] -> advisory]")

advisory = tool.find_action_buttons_docs_shadow(
    listing_row(["[Explore](https://example.com/explore)"]),
    offer_row(["[Website](https://example.com/)", "[Docs](https://example.com/docs)"]),
)
check("the pair is a shadow candidate", advisory is not None, f"got {advisory!r}")
if advisory is not None:
    check(
        "the advisory names the canonical Docs button",
        "referenced offer has [Docs](https://example.com/docs)" in advisory,
        advisory,
    )
    check(
        "the advisory names the overriding button",
        "listing has one non-Docs actionButton [Explore](https://example.com/explore)" in advisory,
        advisory,
    )
    check(
        "the advisory asks for a review decision",
        "review if both actions are appropriate (maximum two buttons)" in advisory,
        advisory,
    )

print("\n[condition 2: listing [Explore, Docs] -> no advisory]")
check(
    "an override that keeps Docs is not a candidate",
    tool.find_action_buttons_docs_shadow(
        listing_row(["[Explore](https://example.com/explore)", "[Docs](https://example.com/docs)"]),
        offer_row(["[Website](https://example.com/)", "[Docs](https://example.com/docs)"]),
    )
    is None,
)

print("\n[condition 3: canonical without Docs -> no advisory]")
check(
    "a canonical offer without a Docs button is not a candidate",
    tool.find_action_buttons_docs_shadow(
        listing_row(["[Explore](https://example.com/explore)"]),
        offer_row(["[Website](https://example.com/)", "[Buy](https://example.com/buy)"]),
    )
    is None,
)
check(
    "a Docs-like label that is not exactly Docs does not count",
    tool.find_action_buttons_docs_shadow(
        listing_row(["[Explore](https://example.com/explore)"]),
        offer_row(["[Website](https://example.com/)", "[Filecoin Docs](https://example.com/docs)"]),
    )
    is None,
)

print("\n[condition 4: override with two buttons -> no advisory by default]")
check(
    "a two-button override is not a candidate",
    tool.find_action_buttons_docs_shadow(
        listing_row(["[Explore](https://example.com/explore)", "[Buy](https://example.com/buy)"]),
        offer_row(["[Website](https://example.com/)", "[Docs](https://example.com/docs)"]),
    )
    is None,
)

# ─────────────────────────────────────────────────────────────────────────────
# [the edges the four conditions do not spell out]
# ─────────────────────────────────────────────────────────────────────────────
print("\n[edges: inheritance, missing values, malformed cells]")
check(
    "a listing without actionButtons inherits the canonical array (no advisory)",
    tool.find_action_buttons_docs_shadow(listing_row(None), offer_row(["[Docs](https://example.com/docs)"])) is None,
)
check(
    "a blank string override inherits the canonical array (no advisory)",
    tool.find_action_buttons_docs_shadow(listing_row(""), offer_row(["[Docs](https://example.com/docs)"])) is None,
)
check(
    "a canonical offer without actionButtons is not a candidate",
    tool.find_action_buttons_docs_shadow(listing_row(["[Explore](https://example.com/explore)"]), offer_row(None)) is None,
)
check(
    "an empty override array is not a one-button override",
    tool.find_action_buttons_docs_shadow(listing_row([]), offer_row(["[Docs](https://example.com/docs)"])) is None,
)
check(
    "a Docs-only override is not a candidate",
    tool.find_action_buttons_docs_shadow(
        listing_row(["[Docs](https://example.com/docs)"]),
        offer_row(["[Website](https://example.com/)", "[Docs](https://example.com/docs)"]),
    )
    is None,
)
check(
    "an unparseable override is not a candidate",
    tool.find_action_buttons_docs_shadow(listing_row("[not json"), offer_row(["[Docs](https://example.com/docs)"])) is None,
)
check(
    "a JSON object override is not a candidate",
    tool.find_action_buttons_docs_shadow(
        listing_row('{"label": "Explore"}'), offer_row(["[Docs](https://example.com/docs)"])
    )
    is None,
)
check(
    "a non-string button inside the override cannot be a Docs button",
    tool.find_action_buttons_docs_shadow(
        listing_row([{"label": "Explore"}]), offer_row(["[Docs](https://example.com/docs)"])
    )
    is not None,
)
check(
    "raw CSV strings are accepted as well as parsed lists",
    tool.find_action_buttons_docs_shadow(
        listing_row('["[Explore](https://example.com/explore)"]'),
        offer_row('["[Website](https://example.com/)","[Docs](https://example.com/docs)"]'),
    )
    is not None,
)

# ─────────────────────────────────────────────────────────────────────────────
# [wiring: resolve_offers must call the check and print the advisory]
# ─────────────────────────────────────────────────────────────────────────────
print("\n[wiring: the advisory is reachable from offer resolution]")

resolve_src = _inspect.getsource(tool.resolve_offers)
check(
    "resolve_offers calls find_action_buttons_docs_shadow",
    "find_action_buttons_docs_shadow(" in resolve_src,
)
check(
    "the call passes the listing row and the canonical offer row",
    "find_action_buttons_docs_shadow(item, offer_row)" in resolve_src,
    "the shadow is a property of the pair, so both rows must be in scope",
)
check(
    "the advisory is printed with the documented prefix",
    '"WARNING: actionButtons_docs_shadowed: "' in resolve_src,
)
check(
    "the advisory names network, category and listing slug",
    "{network_name}/{category}/{item.get('slug')}" in resolve_src,
)

# ─────────────────────────────────────────────────────────────────────────────
# [end-to-end: the tool warns once and leaves the JSON untouched]
# ─────────────────────────────────────────────────────────────────────────────
print("\n[end-to-end: the tool warns for the shadowed row and changes no output]")


def stage_e2e() -> pathlib.Path:
    """Materialise the fixture tree in a temp dir; the tool writes json/ into cwd."""
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="abds-e2e-"))
    shutil.copytree(E2E_ROOT, tmp, dirs_exist_ok=True)
    # git does not track empty directories: the two directories the tool lists
    # unconditionally are created here rather than expected to survive a checkout.
    (tmp / "listings" / "all-networks").mkdir(parents=True, exist_ok=True)
    (tmp / "listings" / "specific-networks" / "demo").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        FIXTURES / "listings.apis.csv",
        tmp / "listings" / "specific-networks" / "demo" / "apis.csv",
    )
    return tmp


tmp = stage_e2e()
try:
    proc = subprocess.run(
        [sys.executable, str(REPO / "tools" / "csv_to_json.py")],
        cwd=str(tmp),
        capture_output=True,
        text=True,
        timeout=180,
    )
    check("the run exits zero (the advisory is not an error)", proc.returncode == 0, f"rc={proc.returncode}")
    advisory_lines = [ln for ln in proc.stdout.splitlines() if ln.startswith(ADVISORY_PREFIX)]
    check(
        "exactly one advisory is reported",
        len(advisory_lines) == 1,
        f"got {len(advisory_lines)}: {advisory_lines}",
    )
    if advisory_lines:
        check(
            "the advisory names network, category and slug",
            advisory_lines[0] == f"{ADVISORY_PREFIX}demo/apis/demo-shadow",
            advisory_lines[0],
        )
    check(
        "the canonical Docs button is named",
        "referenced offer has [Docs](https://example.com/docs)" in proc.stdout,
        proc.stdout[-400:],
    )
    check(
        "the overriding button is named",
        "listing has one non-Docs actionButton [Explore](https://example.com/explore)" in proc.stdout,
        proc.stdout[-400:],
    )
    check(
        "the two-button control row is silent",
        "demo/apis/demo-twobutton" not in proc.stdout,
        proc.stdout[-400:],
    )
    check(
        "the no-Docs-offer control row is silent",
        "demo/apis/demo-nodocs-offer" not in proc.stdout,
        proc.stdout[-400:],
    )
    written = tmp / "json" / "demo.json"
    check("json/demo.json is written", written.exists())
    if written.exists():
        data = json.loads(written.read_text(encoding="utf-8"))
        by_slug = {w.get("slug"): w for w in data.get("apis", [])}
        check(
            "the shadowed row keeps only its override button",
            by_slug.get("demo-shadow", {}).get("actionButtons")
            == ["[Explore](https://example.com/explore)"],
            str(by_slug.get("demo-shadow", {}).get("actionButtons")),
        )
        check(
            "the control row keeps its two buttons",
            by_slug.get("demo-twobutton", {}).get("actionButtons")
            == ["[Explore](https://example.com/explore)", "[Buy](https://example.com/buy)"],
            str(by_slug.get("demo-twobutton", {}).get("actionButtons")),
        )
        check(
            "the inheriting row keeps the canonical Docs button",
            by_slug.get("demo-inherit", {}).get("actionButtons")
            == ["[Website](https://example.com/)", "[Docs](https://example.com/docs)"],
            str(by_slug.get("demo-inherit", {}).get("actionButtons")),
        )
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# ─────────────────────────────────────────────────────────────────────────────
# [benchmark: the issue's four-network scan agrees with the tool]
# ─────────────────────────────────────────────────────────────────────────────
print("\n[benchmark: the four-network scan and the tool report the same rows]")

NETWORKS_DIR = REPO / "listings" / "specific-networks"
OFFERS_DIR = REPO / "references" / "offers"


def read_rows(path: pathlib.Path):
    with open(path, newline="", encoding="utf-8") as f:
        return [r for r in csv.reader(f) if r]


def header_map(rows):
    return {name.strip(): i for i, name in enumerate(rows[0])}


def scan_benchmark(root: pathlib.Path) -> set[str]:
    """Independent re-implementation of the issue's bounded scan.

    For each of the four networks, for each category listing, flag rows that
    reference a canonical offer whose actionButtons contain a Docs button while
    the listing's own override is exactly one non-Docs button.
    """
    found = set()
    for network in BENCHMARK_NETWORKS:
        net_dir = root / "listings" / "specific-networks" / network
        if not net_dir.is_dir():
            continue
        for listing_path in sorted(net_dir.glob("*.csv")):
            offer_path = root / "references" / "offers" / listing_path.name
            if not offer_path.exists():
                continue
            offer_rows = read_rows(offer_path)
            offer_hdr = header_map(offer_rows)
            listing_rows = read_rows(listing_path)
            listing_hdr = header_map(listing_rows)
            if "actionButtons" not in offer_hdr or "actionButtons" not in listing_hdr:
                continue
            offers_by_slug = {}
            for r in offer_rows[1:]:
                if len(r) > offer_hdr.get("slug", 0):
                    offers_by_slug[r[offer_hdr["slug"]]] = r
            for r in listing_rows[1:]:
                if "offer" not in listing_hdr or "slug" not in listing_hdr:
                    continue
                if len(r) <= max(listing_hdr["offer"], listing_hdr["slug"], listing_hdr["actionButtons"]):
                    continue
                ref = r[listing_hdr["offer"]]
                if not (isinstance(ref, str) and ref.startswith("!offer:")):
                    continue
                offer_row = offers_by_slug.get(ref[len("!offer:"):])
                if offer_row is None:
                    continue
                if len(offer_row) <= offer_hdr["actionButtons"]:
                    continue
                if tool.find_action_buttons_docs_shadow(
                    {"actionButtons": r[listing_hdr["actionButtons"]]},
                    {"actionButtons": offer_row[offer_hdr["actionButtons"]]},
                ):
                    found.add(f"{network}/{listing_path.stem}/{r[listing_hdr['slug']]}")
    return found


if NETWORKS_DIR.is_dir() and OFFERS_DIR.is_dir():
    scanned = scan_benchmark(REPO)
    check("the scan finds candidates in this tree", len(scanned) > 0, "no listings data staged?")
    tool_proc = subprocess.run(
        [sys.executable, str(REPO / "tools" / "csv_to_json.py")],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=600,
    )
    reported = set()
    for line in tool_proc.stdout.splitlines():
        if line.startswith(ADVISORY_PREFIX):
            reported.add(line[len(ADVISORY_PREFIX):].strip())
    missing = scanned - reported
    check(
        "every scanned candidate is reported by the tool",
        not missing,
        f"missing: {sorted(missing)[:5]}",
    )
    # The tool may additionally report all-networks rows merged into these
    # networks (the issue's scan is specific-networks only), so the comparison
    # is one-directional by design.
    # The generated JSON is scratch output for this run only.
    shutil.rmtree(REPO / "json", ignore_errors=True)
    print(f"       benchmark candidates in this tree: {len(scanned)}")
else:
    print("       skipped: no listings/ staged in this checkout (tools-only tree)")

print(f"\n{CHECKS - len(FAILURES)}/{CHECKS} checks passed")
if FAILURES:
    print("FAILED:")
    for f in FAILURES:
        print("  -", f)
    raise SystemExit(1)
print("All actionButtons Docs-shadow regression checks passed.")
