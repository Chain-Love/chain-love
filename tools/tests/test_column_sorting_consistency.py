"""Regression tests for bidirectional column sorting consistency (DBIP #4726).

Verifies that:
1. Columns with schema type 'array' (including nullable arrays ['array', 'null'])
   only accept 'arrayLength' (or null) sorting, and reject scalar sorting modes.
2. Columns with scalar schema types (including nullable scalars ['string', 'null'],
   ['boolean', 'null'], integer, number) reject 'arrayLength' sorting.
3. Production meta/columns.json passes validation cleanly.
"""
import copy
import json
import pathlib
import sys
import unittest

ROOT_DIR = pathlib.Path(__file__).resolve().parents[2]
TOOLS_DIR = ROOT_DIR / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import validate


class TestColumnSortingConsistency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(ROOT_DIR / "meta" / "columns.json", "r", encoding="utf-8") as f:
            cls.meta_columns = json.load(f)
        with open(TOOLS_DIR / "schema.json", "r", encoding="utf-8") as f:
            cls.schema = json.load(f)

    def _make_dummy_envelope(self, columns_dict):
        """Construct a minimal envelope matching network JSON layout."""
        return {
            "columns": {"general": list(columns_dict.keys())},
            "meta": {"columns": columns_dict},
        }

    def test_production_meta_columns_zero_errors(self):
        """Production meta/columns.json must pass rule_meta_columns_consistent with zero errors."""
        envelope = self._make_dummy_envelope(self.meta_columns)
        errors = validate.rule_meta_columns_consistent(envelope)
        self.assertEqual(errors, [], f"Unexpected errors in production metadata: {errors}")

    def test_positive_nullable_array_sorting(self):
        """Nullable array properties with arrayLength or null sorting must pass."""
        test_cols = {
            "additionalNotes": copy.deepcopy(self.meta_columns["additionalNotes"]),
            "selfHostedArgs": copy.deepcopy(self.meta_columns["selfHostedArgs"]),
            "actionButtons": copy.deepcopy(self.meta_columns["actionButtons"]),
        }
        self.assertEqual(test_cols["additionalNotes"]["sorting"], "arrayLength")
        self.assertEqual(test_cols["selfHostedArgs"]["sorting"], "arrayLength")
        self.assertIsNone(test_cols["actionButtons"]["sorting"])

        envelope = self._make_dummy_envelope(test_cols)
        errors = validate.rule_meta_columns_consistent(envelope)
        self.assertEqual(errors, [])

    def test_negative_nullable_array_scalar_sorting(self):
        """Nullable array property configured with scalar sorting must be rejected."""
        for bad_sort in ("string", "number", "boolean", "date"):
            test_cols = {
                "additionalNotes": copy.deepcopy(self.meta_columns["additionalNotes"])
            }
            test_cols["additionalNotes"]["sorting"] = bad_sort
            envelope = self._make_dummy_envelope(test_cols)
            errors = validate.rule_meta_columns_consistent(envelope)
            self.assertTrue(
                any("has schema type array but scalar sorting" in e for e in errors),
                f"Expected scalar sorting error for {bad_sort}, got {errors}",
            )

    def test_positive_nullable_scalar_sorting(self):
        """Nullable scalar properties (agentURI, agentURIType, agentWallet) with scalar/null sorting must pass."""
        test_cols = {
            "agentURI": copy.deepcopy(self.meta_columns["agentURI"]),
            "agentURIType": copy.deepcopy(self.meta_columns["agentURIType"]),
            "agentWallet": copy.deepcopy(self.meta_columns["agentWallet"]),
        }
        self.assertEqual(test_cols["agentURI"]["sorting"], "string")
        self.assertEqual(test_cols["agentURIType"]["sorting"], "string")
        self.assertEqual(test_cols["agentWallet"]["sorting"], "string")

        envelope = self._make_dummy_envelope(test_cols)
        errors = validate.rule_meta_columns_consistent(envelope)
        self.assertEqual(errors, [])

    def test_negative_scalar_arraylength_sorting(self):
        """Scalar properties (nullable or required) with arrayLength sorting must be rejected."""
        # Test agentURI, agentURIType, agentWallet (nullable scalars) and price (scalar string)
        for scalar_key in ("agentURI", "agentURIType", "agentWallet", "price", "description"):
            test_cols = {
                scalar_key: copy.deepcopy(self.meta_columns[scalar_key])
            }
            test_cols[scalar_key]["sorting"] = "arrayLength"
            envelope = self._make_dummy_envelope(test_cols)
            errors = validate.rule_meta_columns_consistent(envelope)
            self.assertTrue(
                any("has scalar schema type but arrayLength sorting" in e for e in errors),
                f"Expected scalar arrayLength rejection for {scalar_key}, got {errors}",
            )


if __name__ == "__main__":
    unittest.main()
