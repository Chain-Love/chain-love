import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jsonschema import Draft202012Validator

from validate import make_network_validator

ROW_REF = {"$ref": "#/$defs/row"}
SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$defs": {
        "row": {"type": "object", "required": ["flag"], "properties": {"flag": {"type": "boolean"}}},
        "count": {"type": "object", "required": ["flag"], "properties": {"flag": {"type": "integer"}}},
    },
    "properties": {
        "rows": {"type": "array", "items": ROW_REF},
        "counts": {"type": "array", "items": {"$ref": "#/$defs/count"}},
        "named": {"type": "array", "items": {**ROW_REF, "required": ["name"]}},
    },
}
SCRIPT = Path(__file__).with_name("validate.py")


def diagnostics(validator, document):
    return [(list(e.absolute_path), list(e.absolute_schema_path), e.message)
            for e in validator.iter_errors(document)]


class TestNetworkSchemaCache(unittest.TestCase):
    def test_reuses_successes_across_networks_and_honors_eviction(self):
        checker = Mock(wraps=Draft202012Validator.VALIDATORS["$ref"])
        with patch.dict(Draft202012Validator.VALIDATORS, {"$ref": checker}):
            validator = make_network_validator(SCHEMA, max_entries=2)
            for flag, slug in [(True, "a"), (False, "b"), (True, "a"), (True, "c"), (False, "b")]:
                self.assertTrue(validator.is_valid({"rows": [{"flag": flag, "slug": slug}]}))
            self.assertEqual(checker.call_count, 4)
            # The same JSON object in another key order hits the most recent entry.
            self.assertTrue(validator.is_valid({"rows": [{"slug": "b", "flag": False}]}))
            self.assertEqual(checker.call_count, 4)
            self.assertTrue(make_network_validator(SCHEMA).is_valid({"rows": [{"slug": "b", "flag": False}]}))
            self.assertEqual(checker.call_count, 5)

    def test_errors_keep_their_index_schema_path_and_message(self):
        document = {"rows": [{"flag": True}, {"flag": True}, {"flag": 1}, {"flag": 1}, {}]}
        expected = diagnostics(Draft202012Validator(SCHEMA), document)
        self.assertEqual([e[0] for e in expected], [["rows", 2, "flag"], ["rows", 3, "flag"], ["rows", 4]])
        validator = make_network_validator(SCHEMA)
        self.assertEqual(diagnostics(validator, document), expected)
        self.assertEqual(diagnostics(validator, document), expected)

    def test_each_definition_and_ref_sibling_runs_independently(self):
        row = {"flag": True}
        document = {"rows": [row], "counts": [row], "named": [row]}
        expected = diagnostics(Draft202012Validator(SCHEMA), document)
        self.assertEqual([e[0] for e in expected], [["counts", 0, "flag"], ["named", 0]])
        self.assertEqual(diagnostics(make_network_validator(SCHEMA), document), expected)

    def test_unkeyable_and_oversized_rows_are_validated_every_time(self):
        for extra in ("\ud800", float("nan"), float("inf"), float("-inf"), "large" * 100):
            with self.subTest(extra=extra):
                checker = Mock(wraps=Draft202012Validator.VALIDATORS["$ref"])
                row = {"flag": True, "extra": extra}
                with patch.dict(Draft202012Validator.VALIDATORS, {"$ref": checker}):
                    validator = make_network_validator(SCHEMA, max_key_bytes=100)
                    self.assertTrue(validator.is_valid({"rows": [row, row]}))
                    self.assertEqual(checker.call_count, 2)
                invalid = {"rows": [{**row, "flag": "wrong"}]}
                self.assertEqual(diagnostics(validator, invalid), diagnostics(Draft202012Validator(SCHEMA), invalid))

    def test_scoped_schemas_and_external_refs_use_stock_validation(self):
        for change in (
            {"$schema": "http://json-schema.org/draft-07/schema#"},
            {"$defs": {"row": {"$id": "other.json"}}},
            {"$defs": {"row": {"$dynamicRef": "#here"}}},
            {"allOf": [{"unevaluatedProperties": False}]},
            {"properties": {"row": {"$ref": "other.json"}}},
        ):
            with self.subTest(change=change):
                self.assertIs(type(make_network_validator({**SCHEMA, **change})), Draft202012Validator)

    def test_cli_still_reports_cross_row_errors_after_a_cache_hit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "json").mkdir()
            (root / "references" / "offers").mkdir(parents=True)
            (root / "schema.json").write_text(json.dumps(SCHEMA), encoding="utf-8")
            row = {"flag": True, "slug": "same"}
            (root / "json" / "network.json").write_text(json.dumps({"rows": [row, row]}), encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT)], cwd=root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("Error validating rows: Item 1: Duplicate slug 'same'", result.stdout)


if __name__ == "__main__":
    unittest.main()
