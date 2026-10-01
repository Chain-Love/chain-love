"""Unit tests for rule_actionbuttons_unique_destinations (DBIP #3969).

Run: python3 tools/test_actionbuttons_rule.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from validate_csv import (
    normalize_action_button_destination,
    rule_actionbuttons_unique_destinations,
)

PATH = Path("references/offers/mcpservers.csv")


def cell(pairs):
    return json.dumps([f"[{label}]({url})" for label, url in pairs])


def rows(actionbuttons, slug="example-mcp"):
    return [
        {"slug": "aaa-first", "actionButtons": "[]"},
        {"slug": slug, "actionButtons": actionbuttons},
    ]


def test_duplicate_destination_reported_with_labels_and_url():
    errs = rule_actionbuttons_unique_destinations(
        PATH,
        rows(cell([("Website", "https://docs.base.org/get-started/docs-mcp"),
                   ("Docs", "https://docs.base.org/get-started/docs-mcp")])),
    )
    assert len(errs) == 1, errs
    e = errs[0]
    assert "references/offers/mcpservers.csv" in e
    assert "example-mcp" in e
    assert "https://docs.base.org/get-started/docs-mcp" in e
    assert '"Website"' in e and '"Docs"' in e


def test_trailing_slash_is_same_destination():
    errs = rule_actionbuttons_unique_destinations(
        PATH,
        rows(cell([("Explore", "https://steexp.com/"), ("Docs", "https://steexp.com")])),
    )
    assert len(errs) == 1, errs


def test_scheme_and_host_casing_normalized():
    errs = rule_actionbuttons_unique_destinations(
        PATH,
        rows(cell([("Website", "https://UniversalX.app/"), ("Docs", "https://universalx.app")])),
    )
    assert len(errs) == 1, errs


def test_distinct_destinations_pass():
    errs = rule_actionbuttons_unique_destinations(
        PATH,
        rows(cell([("Website", "https://example.com"), ("Docs", "https://example.com/docs")])),
    )
    assert errs == [], errs


def test_query_difference_is_distinct():
    errs = rule_actionbuttons_unique_destinations(
        PATH,
        rows(cell([("Docs", "https://example.com/docs?tab=1"),
                   ("Guide", "https://example.com/docs?tab=2")])),
    )
    assert errs == [], errs


def test_mailto_and_relative_dup_detected_plain_valid():
    errs = rule_actionbuttons_unique_destinations(
        PATH,
        rows(cell([("Email", "mailto:Hi@Example.com"), ("Contact", "mailto:hi@example.com")])),
    )
    assert len(errs) == 1, errs
    errs = rule_actionbuttons_unique_destinations(
        PATH,
        rows(cell([("Home", "/"), ("Dashboard", "/dashboard")])),
    )
    assert errs == [], errs


def test_non_markdown_and_empty_cells_ignored():
    errs = rule_actionbuttons_unique_destinations(
        PATH,
        rows("not json at all"),
    )
    assert errs == [], errs
    errs = rule_actionbuttons_unique_destinations(PATH, rows(""))
    assert errs == [], errs
    errs = rule_actionbuttons_unique_destinations(
        PATH, rows(json.dumps(["plain-text-no-link", "plain-text-no-link"]))
    )
    assert errs == [], errs


def test_normalize_unit():
    assert normalize_action_button_destination("https://A.example/Path/") == "https://a.example/Path"
    assert normalize_action_button_destination("https://a.example") == "https://a.example/"
    assert normalize_action_button_destination("mailto:X@Y.com") == "mailto:x@y.com"
    assert normalize_action_button_destination("/campaign/") == "/campaign"


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok: {t.__name__}")
    print(f"test_actionbuttons_rule: {len(tests)} passed")


if __name__ == "__main__":
    main()
