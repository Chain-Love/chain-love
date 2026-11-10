import json
from pathlib import Path
import sys
import unittest

from jsonschema import Draft202012Validator

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))
from csv_to_json import normalize  # noqa: E402
from validate import make_providers_schema  # noqa: E402


def sample_api_csv_row(technology: str = "EVM JSON-RPC") -> dict:
    return {
        "slug": "publicnode-avalanche-c-chain-rpc",
        "provider": "PublicNode",
        "offer": "",
        "planType": "Public",
        "planName": "",
        "apiType": "Shared",
        "chain": "mainnet",
        "address": "https://avalanche-c-chain-rpc.publicnode.com",
        "accessPrice": "$0",
        "queryPrice": "$0",
        "uptimeSla": "",
        "bandwidthSla": "",
        "blocksBehindSla": "",
        "starred": "FALSE",
        "trial": "FALSE",
        "availableApis": '["eth","net","web3"]',
        "limitations": "",
        "securityImprovements": "",
        "monitoringAndAnalytics": "",
        "regions": "",
        "actionButtons": '["[Website](https://publicnode.com)"]',
        "supportSla": "",
        "technology": technology,
        "additionalFeatures": "",
        "historicalData": "Pruned",
        "tag": "",
    }


class ApisTechnologyNullableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads((TOOLS_DIR / "schema.json").read_text(encoding="utf-8"))
        cls.validator = Draft202012Validator(cls.schema)
        cls.offers_validator = Draft202012Validator(make_providers_schema(cls.schema))

    def test_nonempty_blank_csv_and_direct_empty_string_pass(self):
        for cell, expected in [("EVM JSON-RPC", "EVM JSON-RPC"), ("", None), ("   ", None), ("NULL", None)]:
            normalized, errors = normalize({"apis": [sample_api_csv_row(cell)]})
            self.assertEqual(errors, [])
            self.assertEqual(normalized["apis"][0]["technology"], expected)
            self.assertTrue(self.validator.is_valid(normalized))
            self.assertTrue(self.offers_validator.is_valid(normalized))
        direct, _ = normalize({"apis": [sample_api_csv_row("REST API")]})
        direct["apis"][0]["technology"] = ""
        self.assertTrue(self.validator.is_valid(direct))

    def test_missing_key_invalid_types_and_other_categories_unchanged(self):
        base, _ = normalize({"apis": [sample_api_csv_row("EVM JSON-RPC")]})
        missing = dict(base["apis"][0])
        del missing["technology"]
        self.assertFalse(self.validator.is_valid({"apis": [missing]}))
        for bad in (123, True, False, [], {}):
            candidate = dict(base["apis"][0], technology=bad)
            self.assertFalse(self.validator.is_valid({"apis": [candidate]}))
        tech_prop = self.schema["$defs"]["apis"]["properties"]["technology"]
        self.assertEqual(tech_prop["examples"], ["EVM JSON-RPC", "The Graph"])
        self.assertIn("technology", self.schema["$defs"]["apis"]["required"])
        for cat in ("explorers", "oracles", "bridges"):
            self.assertEqual(self.schema["$defs"][cat]["properties"]["technology"]["type"], "string")


if __name__ == "__main__":
    unittest.main()
