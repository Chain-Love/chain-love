import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from jsonschema import Draft202012Validator


TOOLS = Path(__file__).resolve().parents[1]


class ProviderLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write_csv(self, relative, fields, rows):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def providers(self, status="", parent="", legacy=False):
        fields = ["slug", "name"]
        rows = [{"slug": "child", "name": "Child"},
                {"slug": "parent", "name": "Parent"}]
        if not legacy:
            fields += ["providerStatus", "parentProvider"]
            rows[0].update(providerStatus=status, parentProvider=parent)
            rows[1].update(providerStatus="active", parentProvider="")
        self.write_csv("references/providers/providers.csv", fields, rows)

    def run_script(self, name):
        return subprocess.run(
            [sys.executable, str(TOOLS / name)], cwd=self.root,
            capture_output=True, text=True, timeout=30,
        )

    def assert_csv_valid(self):
        result = self.run_script("validate_csv.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def assert_csv_invalid(self, message):
        result = self.run_script("validate_csv.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(message, result.stdout)

    def test_all_supported_statuses_and_blank(self):
        for status in ("", "active", "acquired", "renamed", "sunset", "retired", "unknown"):
            with self.subTest(status=status):
                self.providers(status, "parent" if status in ("acquired", "renamed") else "")
                self.assert_csv_valid()

    def test_legacy_columns_remain_optional(self):
        self.providers(legacy=True)
        self.assert_csv_valid()

    def test_invalid_status_is_rejected(self):
        self.providers("unsupported")
        self.assert_csv_invalid("providerStatus 'unsupported' is invalid")

    def test_parent_disallowed_without_transition_status(self):
        for status in ("", "active", "sunset", "retired", "unknown"):
            with self.subTest(status=status):
                self.providers(status, "parent")
                self.assert_csv_invalid("parentProvider requires providerStatus=acquired or renamed")

    def test_transition_requires_parent(self):
        for status in ("acquired", "renamed"):
            with self.subTest(status=status):
                self.providers(status)
                self.assert_csv_invalid(f"providerStatus={status} requires parentProvider")

    def test_parent_must_reference_existing_slug(self):
        self.providers("acquired", "missing")
        self.assert_csv_invalid("parentProvider 'missing' does not match a provider slug")

    def test_generated_metadata_preserves_lifecycle_and_validates_schema(self):
        # Exercise CSV loading, normalization, category collection and JSON output together.
        self.write_csv("listings/specific-networks/test/apis.csv",
                       ["slug", "provider"], [{"slug": "child-api", "provider": "Child"}])
        (self.root / "meta").mkdir()
        (self.root / "listings/all-networks").mkdir()
        (self.root / "references/offers").mkdir(parents=True)
        for name in ("categories", "columns"):
            (self.root / "meta" / f"{name}.json").write_text("{}", encoding="utf-8")
        schema = json.loads((TOOLS / "schema.json").read_text(encoding="utf-8"))
        provider_schema = schema["$defs"]["providerMeta"]
        validator = Draft202012Validator(provider_schema)
        for status, parent in (("acquired", "parent"), ("renamed", "parent"), ("active", ""), ("", "")):
            with self.subTest(status=status):
                self.providers(status, parent)
                self.assert_csv_valid()
                result = self.run_script("csv_to_json.py")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                output = json.loads((self.root / "json/test.json").read_text(encoding="utf-8"))
                provider = output["meta"]["providers"]["child"]
                self.assertEqual(provider["providerStatus"], status or None)
                self.assertEqual(provider["parentProvider"], parent or None)
                self.assertEqual(provider["categories"], ["apis"])
                self.assertEqual(list(validator.iter_errors(provider)), [])
                invalid = dict(provider, providerStatus="unsupported")
                self.assertTrue(list(validator.iter_errors(invalid)))


if __name__ == "__main__":
    unittest.main()
