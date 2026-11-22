import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from validate_csv import rule_provider_identity_unique

SCRIPT = Path(__file__).resolve().parent / "validate_csv.py"
PROVIDERS = Path("references/providers/providers.csv")


def provider(slug, website="", x="", linkedin="", github=""):
    return {"slug": slug, "website": website, "x": x, "linkedin": linkedin, "github": github}


def check(*rows, path=PROVIDERS):
    return rule_provider_identity_unique(path, list(rows))


class TestProviderIdentityUnique(unittest.TestCase):
    def test_distinct_blank_and_same_host_values_pass(self):
        self.assertEqual(check(
            provider("alpha", "https://alpha.example/", "alpha", "company/alpha", github="shared-org"),
            provider("beta", "https://beta.example/", "beta", "company/beta", github="shared-org"),
            provider("gamma"), provider("delta", website=" ", x="", linkedin=None),
            provider("host-wallet", "https://example.com/wallet"), provider("host-cloud", "https://example.com/cloud/"),
        ), [])

    def test_same_website_after_normalizing_fails(self):
        self.assertEqual(check(
            provider("alpha", website="https://www.alpha.example/"),
            provider("beta", website="http://Alpha.example?ref=list#top"),
            provider("gamma", website="https://alpha.example#about"),
        ), [
            f"{PROVIDERS}: row 3: column 'website': 'http://Alpha.example?ref=list#top' is already used by provider 'alpha' (row 2); one row per provider",
            f"{PROVIDERS}: row 4: column 'website': 'https://alpha.example#about' is already used by provider 'alpha' (row 2); one row per provider",
        ])

    def test_same_x_or_linkedin_ignoring_case_and_at_fails(self):
        self.assertEqual(check(
            provider("alpha", x="alpha_io", linkedin="company/alpha-io"),
            provider("beta", x="@Alpha_IO", linkedin="Company/Alpha-IO/"),
        ), [
            f"{PROVIDERS}: row 3: column 'x': '@Alpha_IO' is already used by provider 'alpha' (row 2); one row per provider",
            f"{PROVIDERS}: row 3: column 'linkedin': 'Company/Alpha-IO/' is already used by provider 'alpha' (row 2); one row per provider",
        ])

    def test_other_files_are_skipped(self):
        rows = (provider("alpha", "https://alpha.example", "alpha"), provider("beta", "https://alpha.example", "alpha"))
        self.assertEqual(check(*rows, path=Path("references/offers/apis.csv")), [])
        self.assertEqual(check(*rows, path=Path("json-tools/references/providers/providers.csv")), [])
        self.assertEqual(len(check(*rows)), 2)

    def test_script_reports_repeated_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / PROVIDERS).parent.mkdir(parents=True)
            (Path(tmp) / PROVIDERS).write_text("slug,x\nalpha,alpha_io\nbeta,Alpha_io\n", encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT)], cwd=tmp, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("row 3: column 'x': 'Alpha_io' is already used by provider 'alpha' (row 2); one row per provider", result.stdout)


if __name__ == "__main__":
    unittest.main()
