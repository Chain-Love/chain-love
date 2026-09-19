import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "tools" / "csv_to_json.py"
SPEC = importlib.util.spec_from_file_location("csv_to_json", MODULE_PATH)
csv_to_json = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(csv_to_json)


class ProviderSlugValidationTests(unittest.TestCase):
    def test_rejects_duplicate_provider_slugs(self):
        providers = [
            {"name": "First Provider", "slug": "duplicate"},
            {"name": "Second Provider", "slug": "duplicate"},
        ]

        with self.assertRaisesRegex(
            ValueError, r"Duplicate slugs in providers/providers\.csv: duplicate"
        ):
            csv_to_json.build_index_by_slug(
                providers, label="providers/providers.csv"
            )

    def test_keeps_unique_provider_slugs(self):
        providers = [
            {"name": "First Provider", "slug": "first"},
            {"name": "Second Provider", "slug": "second"},
        ]

        index = csv_to_json.build_index_by_slug(
            providers, label="providers/providers.csv"
        )

        self.assertEqual(set(index), {"first", "second"})


if __name__ == "__main__":
    unittest.main()
