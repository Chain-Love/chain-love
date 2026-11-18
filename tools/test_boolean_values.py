import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from validate_csv import boolean_columns, rule_boolean_values

SCRIPT = Path(__file__).resolve().parent / "validate_csv.py"
WALLETS = Path("listings/specific-networks/algorand/wallets.csv")


class TestBooleanValues(unittest.TestCase):
    def test_columns_come_from_schema(self):
        columns = boolean_columns()
        self.assertIn("evm", columns["wallets"])
        self.assertIn("trial", columns["platforms"])  # declared as "type": ["boolean"]
        self.assertEqual(columns["providers"], ["starred"])
        self.assertNotIn("slug", columns["wallets"])

    def test_uppercase_and_blank_cells_pass(self):
        rows = [{"slug": "a", "evm": "TRUE", "staking": "FALSE", "mfa": ""}, {"slug": "b"}]
        self.assertEqual(rule_boolean_values(WALLETS, rows), [])

    def test_other_values_fail(self):
        rows = [
            {"slug": "a", "evm": "true", "staking": "False"},
            {"slug": "b", "mfa": " TRUE", "msig": "yes", "native": "1", "tendermint": "null"},
        ]
        errors = rule_boolean_values(WALLETS, rows)
        self.assertEqual(len(errors), 6)
        self.assertEqual(
            errors[0],
            f"{WALLETS}: row 2: column 'evm': boolean value must be TRUE or FALSE (uppercase), got 'true'",
        )

    def test_providers_csv_and_files_without_schema(self):
        rows = [{"slug": "a", "starred": "false"}]
        self.assertEqual(len(rule_boolean_values(Path("references/providers/providers.csv"), rows)), 1)
        self.assertEqual(rule_boolean_values(Path("outreach/registry.csv"), rows), [])

    def test_script_ignores_category_named_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "json-tools" / "tools" / "fixtures" / "wallets.csv"
            path.parent.mkdir(parents=True)
            path.write_text("slug,evm\na-wallet,true\n", encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT)], cwd=tmp, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_script_reports_lowercase_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "references" / "offers" / "faucets.csv"
            path.parent.mkdir(parents=True)
            path.write_text("slug,hasCaptcha\na-faucet,true\n", encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT)], cwd=tmp, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("column 'hasCaptcha': boolean value must be TRUE or FALSE (uppercase), got 'true'", result.stdout)


if __name__ == "__main__":
    unittest.main()
