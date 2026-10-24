#!/usr/bin/env python3
"""Offline unit tests for the provider link provenance gate.

All HTML and Markdown pages here are synthetic. No test makes a network
request; the real HTTP probe is only exercised through its pure formatting
helpers so CI stays fast and deterministic.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import provider_link_provenance as plp

HEADER = (
    "slug,name,logoPath,description,website,docs,x,github,discord,"
    "telegram,linkedin,supportEmail,starred,tag\n"
)


def provider_row(
    slug: str,
    name: str,
    website: str = "",
    docs: str = "",
    github: str = "",
    x: str = "",
    description: str = "A synthetic provider for tests",
) -> str:
    return (
        f'{slug},{name},{slug}.png,"{description}",'
        f"{website},{docs},{x},{github},,,, ,FALSE,\n"
    )


def make_change(
    *,
    slug: str = "acme",
    name: str = "Acme",
    field: str = "docs",
    new: str | None = None,
    old: str = "",
    website: str = "https://acme.dev/",
    docs: str | None = None,
    github: str = "acme/acme",
    changed_fields: list[str] | None = None,
) -> dict:
    if new is None:
        new = docs if docs is not None else "https://docs.acme.dev/"

    provider = {
        "slug": slug,
        "name": name,
        "website": website,
        "docs": docs if docs is not None else (new if field == "docs" else ""),
        "github": github,
    }
    return {
        "slug": slug,
        "field": field,
        "old": old,
        "new": new,
        "provider": provider,
        "changed_fields": changed_fields or [field],
    }


class PositiveEvidenceTests(unittest.TestCase):
    def test_official_provider_readme_crosslink_is_first_party_evidenced(self):
        change = make_change()
        evidence = [
            plp.Evidence(
                url="https://github.com/acme/acme",
                content='<p><a href="https://docs.acme.dev">Documentation</a></p>',
            )
        ]
        reachability = plp.Reachability("reachable", 200)

        result = plp.evaluate_change(change, reachability, evidence)

        self.assertEqual(result["provenance"], plp.FIRST_PARTY_EVIDENCED)
        self.assertEqual(result["reachable"], "reachable")
        self.assertEqual(result["http_status"], 200)
        self.assertEqual(result["evidence_url"], "https://github.com/acme/acme")

    def test_markdown_readme_crosslink_is_first_party_evidenced(self):
        change = make_change(slug="acme", name="Acme", github="acme/acme")
        evidence = [
            plp.Evidence(
                url="https://github.com/acme/acme",
                content="See the [documentation](https://docs.acme.dev/).",
            )
        ]

        result = plp.evaluate_change(
            change, plp.Reachability("reachable", 200), evidence
        )

        self.assertEqual(result["provenance"], plp.FIRST_PARTY_EVIDENCED)

    def test_org_profile_link_to_product_repo_is_provider_wide_evidence(self):
        # Mirrors the corrected Huff trail: the org page links to the
        # maintained successor repository, including a section fragment.
        change = make_change(
            slug="huff",
            name="Huff",
            website="https://github.com/huff-language",
            docs="https://github.com/huff-language/huff2#differences-vs-huff-rs",
            github="huff-language",
            changed_fields=["docs"],
        )
        evidence = [
            plp.Evidence(
                url="https://github.com/huff-language",
                content=(
                    '<a href="https://github.com/huff-language/huff2">'
                    "Huff2 compiler</a>"
                ),
            )
        ]

        result = plp.evaluate_change(
            change, plp.Reachability("reachable", 200), evidence
        )

        self.assertEqual(result["provenance"], plp.FIRST_PARTY_EVIDENCED)
        self.assertIn("section fragment was not separately verified", result["reason"])


    def test_exact_fragment_match_is_not_flagged_as_unverified(self):
        change = make_change(
            slug="huff",
            name="Huff",
            website="https://github.com/huff-language",
            docs="https://github.com/huff-language/huff2#differences-vs-huff-rs",
            github="huff-language",
            changed_fields=["docs"],
        )
        evidence = [
            plp.Evidence(
                url="https://github.com/huff-language",
                content=(
                    '<a href="https://github.com/huff-language/huff2'
                    '#differences-vs-huff-rs">Differences</a>'
                ),
            )
        ]

        result = plp.evaluate_change(
            change, plp.Reachability("reachable", 200), evidence
        )

        self.assertEqual(result["provenance"], plp.FIRST_PARTY_EVIDENCED)
        self.assertNotIn("section fragment was not separately verified", result["reason"])


class NegativeEvidenceTests(unittest.TestCase):
    def test_http_200_gambling_page_without_crosslink_needs_review(self):
        change = make_change(
            slug="huff",
            name="Huff",
            website="",
            docs="https://huff.sh/",
            github="huff-language",
            changed_fields=["website", "docs"],
        )
        reachability = plp.Reachability(
            "reachable", 200, page_title="Situs Slot Gacor Terpercaya"
        )

        result = plp.evaluate_change(change, reachability, [])

        self.assertEqual(result["provenance"], plp.NEEDS_REVIEW)
        self.assertEqual(result["reachable"], "reachable")
        self.assertEqual(result["page_title"], "Situs Slot Gacor Terpercaya")
        self.assertIn("No independent first-party crosslink", result["reason"])
        self.assertIn(
            "HTTP reachability does not prove product identity", result["reason"]
        )

    def test_product_scoped_repo_cannot_evidence_provider_wide_docs(self):
        change = make_change(
            slug="wevm",
            name="wevm",
            website="https://wevm.dev/",
            docs="https://viem.sh/docs",
            github="wevm",
            changed_fields=["docs"],
        )
        evidence = [
            plp.Evidence(
                url="https://github.com/wevm/viem",
                content="[Viem documentation](https://viem.sh/docs)",
            )
        ]

        result = plp.evaluate_change(
            change, plp.Reachability("reachable", 200), evidence
        )

        self.assertEqual(result["provenance"], plp.NEEDS_REVIEW)
        self.assertIn("product-scoped", result["reason"])
        self.assertEqual(result["evidence_url"], "https://github.com/wevm/viem")

    def test_same_row_url_is_not_independent_evidence(self):
        change = make_change(
            slug="huff",
            name="Huff",
            website="https://huff.sh/",
            docs="https://huff.sh/",
            github="huff-language",
            changed_fields=["website", "docs"],
        )
        evidence = [
            plp.Evidence(
                url="https://huff.sh/",
                content='<a href="https://huff.sh/">Home</a>',
            )
        ]

        result = plp.evaluate_change(
            change, plp.Reachability("reachable", 200), evidence
        )

        self.assertEqual(result["provenance"], plp.NEEDS_REVIEW)
        self.assertIn("candidate URL itself", result["reason"])

    def test_official_site_is_not_independent_when_website_also_changes(self):
        change = make_change(
            slug="huff",
            name="Huff",
            website="https://huff.sh/",
            docs="https://huff.sh/docs",
            github="huff-language",
            changed_fields=["website", "docs"],
        )
        evidence = [
            plp.Evidence(
                url="https://huff.sh/",
                content='<a href="https://huff.sh/docs">Docs</a>',
            )
        ]

        result = plp.evaluate_change(
            change, plp.Reachability("reachable", 200), evidence
        )

        self.assertEqual(result["provenance"], plp.NEEDS_REVIEW)
        self.assertIn("changed in the same PR", result["reason"])

    def test_evidence_from_unrelated_github_org_is_ignored(self):
        change = make_change(github="acme/acme")
        evidence = [
            plp.Evidence(
                url="https://github.com/not-acme/acme",
                content='<a href="https://docs.acme.dev">Docs</a>',
            )
        ]

        result = plp.evaluate_change(
            change, plp.Reachability("reachable", 200), evidence
        )

        self.assertEqual(result["provenance"], plp.NEEDS_REVIEW)
        self.assertIn("not controlled by this provider", result["reason"])


class UnknownStateTests(unittest.TestCase):
    def test_cloudflare_403_is_unknown_not_hijacked(self):
        change = make_change(
            slug="acme",
            name="Acme",
            docs="https://docs.acme.dev/",
            github="acme/acme",
        )
        reachability = plp.Reachability(
            "blocked_or_unknown", 403, detail="access control or anti-bot response"
        )

        result = plp.evaluate_change(change, reachability, [])

        self.assertEqual(result["provenance"], plp.NEEDS_REVIEW)
        self.assertEqual(result["reachable"], "blocked_or_unknown")
        self.assertIn("not treated as hijack", result["reachability_note"])
        self.assertNotIn("hijacked", result["reason"].lower())

    def test_cloudflare_429_is_unknown_not_hijacked(self):
        change = make_change()
        result = plp.evaluate_change(
            change,
            plp.Reachability("blocked_or_unknown", 429),
            [],
        )

        self.assertEqual(result["provenance"], plp.NEEDS_REVIEW)
        self.assertEqual(result["reachable"], "blocked_or_unknown")
        self.assertIn("HTTP 429", result["reachability_note"])

    def test_cleared_field_is_not_applicable(self):
        change = make_change(field="docs", new="", old="https://docs.acme.dev/")

        result = plp.evaluate_change(change, plp.Reachability("not_applicable"), [])

        self.assertEqual(result["provenance"], plp.NOT_APPLICABLE)
        self.assertEqual(result["reachable"], "not_applicable")

    def test_unreachable_page_is_not_automatically_condemned(self):
        change = make_change()
        result = plp.evaluate_change(
            change, plp.Reachability("unreachable", detail="URLError"), []
        )

        self.assertEqual(result["provenance"], plp.NEEDS_REVIEW)
        self.assertEqual(result["reachable"], "unreachable")
        self.assertIn("unreachable", result["reachability_note"])


class ChangeSetTests(unittest.TestCase):
    def test_only_changed_website_and_docs_are_reported(self):
        old = HEADER + provider_row("acme", "Acme", github="acme/acme")
        new = HEADER + provider_row(
            "acme",
            "Acme",
            website="https://acme.dev",
            github="acme/acme",
            x="acme_new_handle",
        )

        changes = plp.compute_changes(old, new)

        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["field"], "website")
        self.assertEqual(changes[0]["old"], "")
        self.assertEqual(changes[0]["new"], "https://acme.dev")

    def test_unchanged_fields_and_other_columns_are_ignored(self):
        old = HEADER + provider_row(
            "acme", "Acme", website="https://acme.dev", github="acme/acme"
        )
        new = HEADER + provider_row(
            "acme",
            "Acme",
            website="https://acme.dev",
            github="acme/acme",
            x="acme_new_handle",
        )

        self.assertEqual(plp.compute_changes(old, new), [])

    def test_both_fields_report_shared_changed_fields(self):
        old = HEADER + provider_row("huff", "Huff", github="huff-language")
        new = HEADER + provider_row(
            "huff",
            "Huff",
            website="https://huff.sh/",
            docs="https://huff.sh/docs",
            github="huff-language",
        )

        changes = plp.compute_changes(old, new)

        self.assertEqual([item["field"] for item in changes], ["docs", "website"])
        for item in changes:
            self.assertEqual(item["changed_fields"], ["website", "docs"])

    def test_collect_reads_git_refs(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            csv_path = repo / plp.PROVIDERS_PATH
            csv_path.parent.mkdir(parents=True)
            csv_path.write_text(
                HEADER + provider_row("acme", "Acme", github="acme/acme"),
                encoding="utf-8",
            )
            self._commit(repo, "initial provider")

            csv_path.write_text(
                HEADER
                + provider_row(
                    "acme",
                    "Acme",
                    docs="https://docs.acme.dev/",
                    github="acme/acme",
                ),
                encoding="utf-8",
            )
            self._commit(repo, "add docs")

            changes = plp.collect_changes("HEAD~1", "HEAD", cwd=str(repo))

        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["slug"], "acme")
        self.assertEqual(changes[0]["field"], "docs")
        self.assertEqual(changes[0]["new"], "https://docs.acme.dev/")

    def test_collect_rejects_unknown_git_ref(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            self._commit(repo, "empty commit")

            with self.assertRaises(plp.CollectError):
                plp.collect_changes("does-not-exist", "HEAD", cwd=str(repo))

    @staticmethod
    def _commit(repo: Path, message: str) -> None:
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.com",
                "commit",
                "--allow-empty",
                "-qm",
                message,
            ],
            cwd=repo,
            check=True,
        )


class UrlAndExtractionTests(unittest.TestCase):
    def test_normalize_url_ignores_scheme_case_www_and_trailing_slash(self):
        self.assertEqual(
            plp.normalize_url("HTTPS://WWW.Acme.dev/docs/"),
            "https://acme.dev/docs",
        )

    def test_normalize_url_keeps_fragments_distinct(self):
        self.assertNotEqual(
            plp.normalize_url("https://acme.dev/docs#a"),
            plp.normalize_url("https://acme.dev/docs#b"),
        )

    def test_markdown_code_blocks_are_not_crosslinks(self):
        text = (
            "```\n"
            "[old](https://evil.example/docs)\n"
            "```\n"
            "Use the [current docs](https://docs.acme.dev).\n"
        )

        self.assertEqual(plp.extract_markdown_links(text), ["https://docs.acme.dev"])

    def test_markdown_reference_links_are_crosslinks(self):
        text = "See [the docs][1].\n\n[1]: https://docs.acme.dev\n"

        self.assertEqual(plp.extract_markdown_links(text), ["https://docs.acme.dev"])

    def test_safe_fetch_rejects_private_and_non_http_urls(self):
        self.assertTrue(plp.is_safe_fetch_url("https://docs.acme.dev/"))
        self.assertFalse(plp.is_safe_fetch_url("http://127.0.0.1/admin"))
        self.assertFalse(plp.is_safe_fetch_url("http://169.254.169.254/latest"))
        self.assertFalse(plp.is_safe_fetch_url("file:///etc/passwd"))
        self.assertFalse(plp.is_safe_fetch_url("https://example.com:8443/"))


class ReportTests(unittest.TestCase):
    def test_report_exposes_reachable_and_provenance_separately(self):
        change = make_change()
        result = plp.evaluate_change(change, plp.Reachability("reachable", 200), [])

        report = plp.render_report([result], base="origin/main", head="HEAD")

        self.assertIn("| Reachable | Provenance |", report)
        self.assertIn("HTTP success ≠ first-party identity verified", report)
        self.assertIn(plp.NEEDS_REVIEW, report)
        self.assertIn("1 changed field(s)", report)

    def test_report_handles_empty_change_set(self):
        report = plp.render_report([])

        self.assertIn("No new or changed provider", report)

    def test_report_escapes_pipes_in_reason(self):
        result = {
            "slug": "acme",
            "name": "Acme",
            "field": "docs",
            "url": "https://docs.acme.dev/",
            "reachable": "reachable",
            "http_status": 200,
            "page_title": "",
            "reachability_note": "reachable (HTTP 200)",
            "provenance": plp.NEEDS_REVIEW,
            "reason": "a | b",
            "evidence_url": None,
        }

        report = plp.render_report([result])

        self.assertIn(r"a \| b", report)

    def test_evidence_file_loader_accepts_html_key(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "evidence.json"
            path.write_text(
                json.dumps(
                    {
                        "acme": [
                            {
                                "url": "https://github.com/acme/acme",
                                "html": '<a href="https://docs.acme.dev">Docs</a>',
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            loaded = plp.load_evidence_file(str(path))

        self.assertEqual(len(loaded["acme"]), 1)
        self.assertEqual(loaded["acme"][0].url, "https://github.com/acme/acme")


if __name__ == "__main__":
    unittest.main()
