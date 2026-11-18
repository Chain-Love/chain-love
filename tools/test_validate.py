import copy
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


TOOLS = Path(__file__).resolve().parent


class NetworkEnvelopeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "json").mkdir()
        (self.root / "references/offers").mkdir(parents=True)
        (self.root / "schema.json").write_bytes((TOOLS / "schema.json").read_bytes())
        self.offer = {
            "slug": "example-faucet", "provider": "Example",
            "requiresLogin": False, "hasCaptcha": False,
            "requiredMainnetBalance": None, "price": None,
            "dripLimitAmount": None, "dripLimitPeriod": None,
            "additionalNotes": None, "starred": False,
            "actionButtons": None, "tag": None,
        }
        self.network = {
            "schemaVersion": "2.0.0",
            "faucets": [dict(self.offer, chain="testnet")],
            "columns": {"faucets": ["slug"]},
            "meta": {
                "categories": {"faucets": {"key": "faucets", "label": "Faucets"}},
                "columns": {"slug": {"key": "slug", "label": "Slug"}},
            },
        }

    def validate(self, network):
        (self.root / "json/example.json").write_text(json.dumps(network), encoding="utf-8")
        with (self.root / "references/offers/faucets.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=self.offer)
            writer.writeheader()
            writer.writerow({key: json.dumps(value) if not isinstance(value, str) else value
                             for key, value in self.offer.items()})
        return subprocess.run(
            [sys.executable, "-X", "utf8", "-B", str(TOOLS / "validate.py")],
            cwd=self.root, capture_output=True, text=True, encoding="utf-8",
        )

    def test_valid_network_and_bare_offer(self):
        result = self.validate(self.network)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_envelope_fields(self):
        fields = ("schemaVersion", "columns", "meta")
        for missing in [(field,) for field in fields] + [fields]:
            with self.subTest(missing=missing):
                network = copy.deepcopy(self.network)
                for field in missing:
                    del network[field]
                result = self.validate(network)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                for field in missing:
                    self.assertIn(f"'{field}' is a required property", result.stdout)

    def test_empty_network(self):
        result = self.validate({})
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("is a required property", result.stdout)

    def test_wrong_schema_version(self):
        self.network["schemaVersion"] = "1.0.0"
        result = self.validate(self.network)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("'2.0.0' was expected", result.stdout)

    def test_offer_row_requirements_remain_enforced(self):
        del self.offer["provider"]
        result = self.validate(self.network)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("'provider' is a required property", result.stdout)


if __name__ == "__main__":
    unittest.main()
