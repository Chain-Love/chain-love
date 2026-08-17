import csv
import tempfile
import unittest
from pathlib import Path

from tools.validate_csv import (
    CSVValidator,
    rule_json_array_elements_unique,
)


class JsonArrayUniquenessTests(unittest.TestCase):
    def _validate(self, value: str):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["slug", "values"])
                writer.writeheader()
                writer.writerow({"slug": "sample", "values": value})

            validator = CSVValidator()
            validator.add_rule(rule_json_array_elements_unique)
            return validator.validate_file(path)

    def test_duplicate_string_is_reported_with_location(self):
        errors = self._validate('["EN", "KO", "KO"]')

        self.assertEqual(len(errors), 1)
        self.assertIn("row 2: column values", errors[0])
        self.assertIn('duplicate JSON-array element "KO"', errors[0])

    def test_unique_array_is_valid(self):
        self.assertEqual(self._validate('["EN", "KO"]'), [])

    def test_empty_array_is_valid(self):
        self.assertEqual(self._validate("[]"), [])

    def test_exact_json_values_are_type_sensitive(self):
        self.assertEqual(self._validate('[1, true, "1"]'), [])


if __name__ == "__main__":
    unittest.main()
