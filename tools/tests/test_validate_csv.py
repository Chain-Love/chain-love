import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1]))
import validate_csv


class WalletLanguagesRuleTests(unittest.TestCase):
    path = Path("wallets.csv")

    def errors_for(self, value: str):
        return validate_csv.rule_wallet_languages(self.path, [{"languages": value}])

    def test_accepts_canonical_tags_and_blank_inheritance(self):
        for value in ('["en"]', '["pt-BR"]', '["zh-Hant"]', '["fil"]', ""):
            with self.subTest(value=value):
                self.assertEqual(self.errors_for(value), [])

    def test_rejects_legacy_or_ambiguous_values(self):
        for value in (
            '["Recent-State"]',
            '["Custom"]',
            '["Trace"]',
            '["zz"]',
            '["pt-br"]',
            '["en", "EN"]',
        ):
            with self.subTest(value=value):
                self.assertTrue(self.errors_for(value))


if __name__ == "__main__":
    unittest.main()
