import csv
import unittest
from pathlib import Path


class OfferSchemaTests(unittest.TestCase):
    """Guard the common columns shared by every canonical offer category."""

    OFFER_DIRECTORY = Path(__file__).parents[1] / "references" / "offers"

    def test_every_category_declares_tag_once(self):
        category_files = sorted(self.OFFER_DIRECTORY.glob("*.csv"))
        self.assertEqual(
            {path.stem for path in category_files},
            {
                "analytics",
                "apis",
                "bridges",
                "explorers",
                "faucets",
                "mcpservers",
                "oracles",
                "platforms",
                "ramps",
                "sdks",
                "security",
                "services",
                "storages",
                "wallets",
            },
        )

        for category_file in category_files:
            with category_file.open(encoding="utf-8-sig", newline="") as stream:
                header = next(csv.reader(stream))
            columns = [column.strip() for column in header]
            with self.subTest(category=category_file.stem):
                self.assertEqual(columns.count("tag"), 1)


if __name__ == "__main__":
    unittest.main()
