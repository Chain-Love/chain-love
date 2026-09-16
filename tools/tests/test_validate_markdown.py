"""Regression tests for the markdown heuristics in tools/validate.py (DBIP #3656).

Runs with plain `python3` (no pytest) so the required `Validate JSON` check can
call it directly inside the network-disabled container, next to the rest of the
pipeline.

What each block pins down:

* `has_unclosed_markdown` must still catch a stray single-`*` span when the
  cell also holds a `**bold**` span (issue #3656 finding 1), and must stop
  reporting legitimate underscore-bearing text such as URLs and social handles
  (finding 4).
* A URL must not swallow the markup that follows it, and a standalone `_`
  emphasis must be reported whether or not the cell contains any other markup
  (review on #3657).
* `is_markdown_link` must match the whole cell and must not truncate a link
  target that contains parentheses (finding 2).
* `check_validation` must run the schema and rule phases unconditionally and
  report both error sets (the `and` short circuit hid rule errors).
"""
import inspect
import io
import pathlib
import re
import sys
from contextlib import redirect_stdout

HERE = pathlib.Path(__file__).resolve().parent
# Assembled CI workspace: validate.py is copied to the repo root.
# Local checkout: it lives next to this file's parent (tools/).
sys.path.insert(0, str(HERE.parent.parent))
sys.path.insert(0, str(HERE.parent))

import validate  # noqa: E402  (path set up above on purpose)
from validate import (  # noqa: E402
    Validator,
    check_validation,
    has_unclosed_markdown,
    is_markdown_link,
    rule_action_buttons_is_list_of_links,
    rule_chain_is_lowercase,
    rule_no_unclosed_markdown,
    rule_provider_casing_consistent,
    rule_slug_kebab_case,
    rule_slug_unique,
)
from jsonschema import Draft202012Validator  # noqa: E402

# The exact cell quoted in issue #3656 finding 4.
SUBQUERY_DOCS_URL = (
    "https://subquery.network/doc/subquery_network/introduction/introduction.html"
)
# A provider social handle of the kind that fills references/providers/providers.csv.
PROVIDER_HANDLE = "0xppl_"

FAILURES = []


def check(name, condition, detail=""):
    if condition:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}{(': ' + detail) if detail else ''}")
        FAILURES.append(name)


# --------------------------------------------------------------------------
# finding 1: a stray single-* span next to a **bold** span
# --------------------------------------------------------------------------
def test_single_star_span():
    print("has_unclosed_markdown: single-* spans")

    check(
        "'**bold** and *unclosed' is caught (issue #3656 acceptance criterion 1)",
        has_unclosed_markdown("**bold** and *unclosed") is True,
        "returned False - the single-star branch is still skipped when ** is present",
    )
    check("'**bold**' alone is clean", has_unclosed_markdown("**bold**") is False)
    check("'*italic*' alone is clean", has_unclosed_markdown("*italic* text") is False)
    check(
        "'**bold** and *italic*' is clean",
        has_unclosed_markdown("**bold** and *italic*") is False,
    )
    check("'plain text' is clean", has_unclosed_markdown("plain text") is False)
    # pre-existing behaviour that must not regress
    check("unclosed bold is caught", has_unclosed_markdown("**unclosed bold") is True)
    check("unclosed backtick is caught", has_unclosed_markdown("`code") is True)
    check(
        "unbalanced bracket is caught",
        has_unclosed_markdown("[link](https://example.com") is True,
    )
    check("empty string is clean", has_unclosed_markdown("") is False)
    check(
        "a non-string value is clean (JSON list cells reach this rule)",
        has_unclosed_markdown(["[Docs](https://example.com)"]) is False,
    )


# --------------------------------------------------------------------------
# finding 4: underscores in URLs / handles are not broken markdown
# --------------------------------------------------------------------------
def test_underscore_heuristic():
    print("has_unclosed_markdown: underscore scoping")

    check(
        "the subquery docs URL is not flagged (issue #3656 acceptance criterion 4)",
        has_unclosed_markdown(SUBQUERY_DOCS_URL) is False,
        "the URL was reported as unclosed markdown",
    )
    check(
        "a provider handle such as '0xppl_' is not flagged",
        has_unclosed_markdown(PROVIDER_HANDLE) is False,
    )
    check(
        "a snake_case identifier is not flagged",
        has_unclosed_markdown("latest_known_version") is False,
    )
    check(
        "a genuinely unclosed underscore in a markdown cell is still caught",
        has_unclosed_markdown("**Acme** provides _analytics") is True,
    )
    check(
        "an underscore-heavy URL is clean even next to markdown",
        has_unclosed_markdown("See " + SUBQUERY_DOCS_URL + " for **details**") is False,
    )


# --------------------------------------------------------------------------
# review on #3657: markup standing next to a URL was swallowed by the URL
# --------------------------------------------------------------------------
def test_markup_adjacent_to_url():
    print("has_unclosed_markdown: markup adjacent to a URL")

    # The URL body used to accept the markdown delimiter characters, so a "**"
    # that followed a URL was consumed together with the URL and the cell was
    # reported clean. Asserting on URL_RE itself pins the mechanism, not just
    # the verdict: the two can drift apart in a later rewrite.
    check(
        "URL_RE leaves the markup that follows a URL alone",
        validate.URL_RE.sub("", "https://example.com/**unclosed") == "**unclosed",
        "URL_RE consumed the markup: "
        f"{validate.URL_RE.sub('', 'https://example.com/**unclosed')!r}",
    )
    check(
        "'https://example.com/**unclosed' is caught",
        has_unclosed_markdown("https://example.com/**unclosed") is True,
        "the URL swallowed the ** that follows it",
    )
    check(
        "'https://example.com/**' is caught",
        has_unclosed_markdown("https://example.com/**") is True,
    )
    check(
        "an underscore emphasis right after a URL is caught",
        has_unclosed_markdown("Read https://example.com then _unclosed emphasis") is True,
    )
    # controls: a URL must not disable the checks around it
    check(
        "balanced markup adjacent to a URL stays clean",
        has_unclosed_markdown("Docs at https://acme.example/**bold**") is False,
    )
    check(
        "the URL body still ends at the closing bracket of a link",
        has_unclosed_markdown("[Docs](https://en.wikipedia.org/wiki/Chain_(blockchain))") is False,
    )
    # The strip step itself, now that word-internal underscores are ignored even
    # without it: a delimiter-shaped underscore inside a query string still has
    # to disappear with the URL.
    check(
        "a URL whose query holds a boundary underscore is stripped whole",
        has_unclosed_markdown(
            "See https://acme.example/docs?utm_source=_acme_campaign for details"
        )
        is False,
        "the URL was not stripped, so its query string was counted as markup",
    )


# --------------------------------------------------------------------------
# review on #3657: standalone broken emphasis was missed unless the cell also
# happened to contain unrelated markup
# --------------------------------------------------------------------------
def test_underscore_delimiters():
    print("has_unclosed_markdown: underscore delimiters")

    check(
        "a bare '_unclosed' cell is caught",
        has_unclosed_markdown("_unclosed") is True,
        "returned False - the underscore branch is still gated on other markup",
    )
    check(
        "'broken _italic' is caught",
        has_unclosed_markdown("broken _italic") is True,
    )
    check(
        "an opener with no closer after it is caught",
        has_unclosed_markdown("_a_ and _b") is True,
    )
    # word-internal underscores stay data, with or without other markup around
    check(
        "a snake_case identifier next to real markdown is clean",
        has_unclosed_markdown("subquery_network **bold**") is False,
        "the identifier alone was enough to trip the old underscore count",
    )
    check(
        "an identifier inside a code span is clean",
        has_unclosed_markdown("see `subquery_network` here") is False,
    )
    check(
        "closed emphasis is clean",
        has_unclosed_markdown("_italic_ and _bold_") is False,
    )
    # An orphan closer is data rather than an unclosed span (a handle such as
    # 0xppl_), which is why only openers are counted as shortcomings.
    check(
        "a trailing handle underscore is clean",
        has_unclosed_markdown("**bold** " + PROVIDER_HANDLE) is False,
    )


# --------------------------------------------------------------------------
# finding 2: parenthesized link targets must survive, trailing junk must not
# --------------------------------------------------------------------------
def test_markdown_link():
    print("is_markdown_link: full match and intact target")

    cell = "[Docs](https://en.wikipedia.org/wiki/Chain_(blockchain))"
    check("a parenthesized URL is a valid markdown link", is_markdown_link(cell) is True)
    match = validate.MARKDOWN_LINK_RE.fullmatch(cell)
    check(
        "the captured target is not truncated (issue #3656 acceptance criterion 2)",
        match is not None
        and match.group("link") == "https://en.wikipedia.org/wiki/Chain_(blockchain)",
        f"captured {match.group('link')!r}" if match else "no match",
    )
    check(
        "trailing junk after the link is rejected",
        is_markdown_link("[Buy](https://acme.example) buy now") is False,
        "the cell was accepted - the check is not anchored to the whole string",
    )
    check("a plain link is accepted", is_markdown_link("[Docs](https://acme.example)") is True)
    check(
        "the captured target of a plain link is exact",
        validate.MARKDOWN_LINK_RE.fullmatch("[Docs](https://acme.example)").group("link")
        == "https://acme.example",
    )
    check("plain text is not a link", is_markdown_link("not a link") is False)
    check("an empty cell is not a link", is_markdown_link("") is False)
    check("a non-string is not a link", is_markdown_link(["[Docs](https://a.example)"]) is False)


# --------------------------------------------------------------------------
# finding 5: schema and rule phases must both run
# --------------------------------------------------------------------------
def _tiny_schema():
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["services"],
        "properties": {
            "services": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["slug", "price"],
                    "properties": {"slug": {"type": "string"}, "price": {"type": "string"}},
                },
            }
        },
    }


def _rules():
    rules = Validator()
    for rule in (
        rule_slug_unique,
        rule_no_unclosed_markdown,
        rule_action_buttons_is_list_of_links,
        rule_provider_casing_consistent,
        rule_slug_kebab_case,
        rule_chain_is_lowercase,
    ):
        rules.add_rule(rule)
    return rules


def _run(data):
    buf = io.StringIO()
    with redirect_stdout(buf):
        ok = check_validation(
            data=data,
            schema_validator=Draft202012Validator(_tiny_schema()),
            rules_validator=_rules(),
        )
    return ok, buf.getvalue()


def test_error_aggregation():
    print("check_validation: schema and rule phases are both executed")

    # 'Bad_Slug' breaks rule_slug_kebab_case, the missing 'price' breaks the schema.
    ok, out = _run({"services": [{"slug": "Bad_Slug"}]})
    check("a broken row is rejected", ok is False)
    check(
        "the schema error is reported",
        "'price' is a required property" in out,
        out[:200],
    )
    check(
        "the rule error is reported in the same run",
        "must be kebab-case" in out,
        "rule errors are still hidden behind a failing schema phase",
    )

    ok, out = _run({"services": [{"slug": "Bad_Slug", "price": "$0"}]})
    check("a rule-only failure is still rejected", ok is False)
    check("the rule error is reported", "must be kebab-case" in out)

    ok, out = _run({"services": [{"slug": "acme-analytics", "price": "$0"}]})
    check("a clean row is accepted", ok is True, out[:400])


def test_main_wiring():
    print("source wiring")
    src = inspect.getsource(check_validation)
    check("check_validation calls the schema phase", "check_schema_validation(" in src)
    check("check_validation calls the rule phase", "check_rules_validation(" in src)
    check(
        "check_validation does not short circuit on the schema result",
        "return check_schema_validation(schema_validator, data) and check_rules_validation("
        not in src.replace("    ", ""),
        "the phases are chained with a short-circuiting `and` again",
    )
    main_src = inspect.getsource(validate.main)
    check(
        "main() registers the markdown rule",
        "rule_no_unclosed_markdown" in main_src,
    )
    check(
        "main() exits non-zero when any phase fails",
        "exit(1)" in main_src,
    )


def main():
    test_single_star_span()
    test_underscore_heuristic()
    test_markup_adjacent_to_url()
    test_underscore_delimiters()
    test_markdown_link()
    test_error_aggregation()
    test_main_wiring()

    if FAILURES:
        print(f"\n{len(FAILURES)} check(s) failed: {', '.join(FAILURES)}")
        raise SystemExit(1)
    print("\nAll markdown heuristic regression checks passed.")


if __name__ == "__main__":
    main()
