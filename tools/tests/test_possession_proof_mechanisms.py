"""Tests for validate_possession_proof_mechanisms (DBIP #4724)."""
import json, pathlib, sys, unittest, jsonschema
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import csv_to_json as tool
REPO = pathlib.Path(__file__).resolve().parents[2]


class TestPossessionProof(unittest.TestCase):
    def test_validation_rules(self):
        v = tool.validate_possession_proof_mechanisms
        self.assertEqual(v([{"slug": "a", "possessionProofMechanisms": None}, {"slug": "b", "possessionProofMechanisms": []}], "t"), [])
        self.assertEqual(v([{"slug": "c", "possessionProofMechanisms": ["PDP", "PoRep", "PoSt"]}], "t"), [])
        self.assertTrue(any("must be one of" in e for e in v([{"possessionProofMechanisms": ["Invalid"]}], "t")))
        self.assertTrue(any("duplicates mechanism" in e for e in v([{"possessionProofMechanisms": ["PDP", "PDP"]}], "t")))
        self.assertTrue(any("must be sorted alphabetically" in e for e in v([{"possessionProofMechanisms": ["PoSt", "PDP"]}], "t")))
        self.assertTrue(any("must be a JSON array or null" in e for e in v([{"possessionProofMechanisms": "PDP"}], "t")))

    def test_schema(self):
        with open(REPO / "tools" / "schema.json") as f:
            schema = json.load(f)["$defs"]["storages"]
        valid = {"slug": "s", "provider": "p", "toolType": "Storage", "price": "", "tag": ["T"], "description": "d", "starred": False, "actionButtons": ["[W](u)"], "planType": "Free", "possessionProofMechanisms": ["PDP"]}
        self.assertTrue(jsonschema.Draft202012Validator(schema).is_valid(valid))
        self.assertFalse(jsonschema.Draft202012Validator(schema).is_valid({**valid, "possessionProofMechanisms": ["Bad"]}))


if __name__ == "__main__":
    unittest.main()
