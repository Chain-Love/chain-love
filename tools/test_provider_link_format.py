import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from validate_csv import rule_provider_link_format

SCRIPT = Path(__file__).resolve().parent / "validate_csv.py"
PROVIDERS = Path("references/providers/providers.csv")
GOOD = {
    "website": "https://example.com/", "docs": "HTTP://docs.example.com", "x": "example",
    "github": "Chain-Love/chain-love", "discord": "invite/example", "telegram": "example",
    "linkedin": "company/example",
}


def check(path=PROVIDERS, **cells):
    return rule_provider_link_format(path, [{**GOOD, **cells}])


class TestProviderLinkFormat(unittest.TestCase):
    def test_plain_values_and_blank_cells_pass(self):
        self.assertEqual(check(), [])
        self.assertEqual(check(website=" https://example.com/ ", docs="", x="", github=None), [])
        self.assertEqual(check(x="@example", github="d13co/algo.surf", telegram="+AbC", linkedin="in/someone"), [])

    def test_website_and_docs_need_a_full_url(self):
        self.assertEqual(check(website="example.com", docs="https://example.com/a b"), [
            f"{PROVIDERS}: row 2: column 'website': 'example.com' must be a full URL (http:// or https://, no spaces)",
            f"{PROVIDERS}: row 2: column 'docs': 'https://example.com/a b' must be a full URL (http:// or https://, no spaces)",
        ])
        for value in ("https:///missing-host", "https://?q=x", "https://:443", "https://[::1"):
            with self.subTest(value=value):
                self.assertEqual(len(check(website=value, docs=value)), 2)

    def test_platform_columns_reject_urls_domains_and_emails(self):
        errors = check(x="https://x.com/example", github="GitHub.com/a/b", discord="discord.gg/abc",
                       telegram="t.me/example", linkedin="www.linkedin.com/company/example")
        self.assertEqual(len(errors), 5)
        self.assertTrue(all(e.endswith("must store only the part after the domain") for e in errors))
        self.assertEqual(len(check(x="twitter.com/example", github="customercare@transfi.com",
                                   discord="//discord.gg/abc", telegram="http:/t.me/a", linkedin="example")), 5)

    def test_markdown_links_fail_in_every_link_column(self):
        errors = check(**{column: "[Site](https://example.com)" for column in GOOD})
        self.assertEqual(len(errors), 7)
        self.assertTrue(all(e.endswith("must be a plain value, not a Markdown link") for e in errors))

    def test_other_files_and_free_text_are_not_checked(self):
        self.assertEqual(check(Path("references/offers/apis.csv"), website="example.com"), [])
        self.assertEqual(check(Path("json-tools/references/providers/providers.csv"), website="example.com"), [])
        self.assertEqual(check(description="See [docs](https://example.com)"), [])

    def test_script_reports_bad_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / PROVIDERS
            path.parent.mkdir(parents=True)
            path.write_text("slug,github\na,https://github.com/a\n", encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT)], cwd=tmp, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("column 'github': 'https://github.com/a' must store only the part after the domain", result.stdout)


if __name__ == "__main__":
    unittest.main()
