"""Regression tests for validate_possession_proof_mechanisms (DBIP #4724).

Run: python3 tools/tests/test_possession_proof_mechanisms.py
"""
from __future__ import annotations

import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import csv_to_json as tool
import jsonschema

REPO = pathlib.Path(__file__).resolve().parents[2]


class TestPossessionProofMechanismsValidation(unittest.TestCase):
    def test_valid_none_and_empty(self):
        items = [
            {"slug": "test-none", "possessionProofMechanisms": None},
            {"slug": "test-empty", "possessionProofMechanisms": []},
        ]
        errors = tool.validate_possession_proof_mechanisms(items, "test")
        self.assertEqual(errors, [])

    def test_valid_mechanisms_sorted(self):
        items = [
            {"slug": "filecoin-cloud-warm", "possessionProofMechanisms": ["PDP"]},
            {"slug": "filecoin-standard", "possessionProofMechanisms": ["PoRep", "PoSt"]},
            {"slug": "filecoin-all", "possessionProofMechanisms": ["PDP", "PoRep", "PoSt"]},
        ]
        errors = tool.validate_possession_proof_mechanisms(items, "test")
        self.assertEqual(errors, [])

    def test_invalid_mechanism_name(self):
        items = [
            {"slug": "test-unknown", "possessionProofMechanisms": ["PDP", "ProofOfStorage"]},
        ]
        errors = tool.validate_possession_proof_mechanisms(items, "test")
        self.assertTrue(any("must be one of" in e for e in errors))

    def test_duplicate_mechanism(self):
        items = [
            {"slug": "test-dup", "possessionProofMechanisms": ["PDP", "PDP"]},
        ]
        errors = tool.validate_possession_proof_mechanisms(items, "test")
        self.assertTrue(any("duplicates mechanism" in e for e in errors))

    def test_unsorted_mechanisms(self):
        items = [
            {"slug": "test-unsorted", "possessionProofMechanisms": ["PoSt", "PDP"]},
        ]
        errors = tool.validate_possession_proof_mechanisms(items, "test")
        self.assertTrue(any("must be sorted alphabetically" in e for e in errors))

    def test_non_array_value(self):
        items = [
            {"slug": "test-scalar", "possessionProofMechanisms": "PDP"},
        ]
        errors = tool.validate_possession_proof_mechanisms(items, "test")
        self.assertTrue(any("must be a JSON array or null" in e for e in errors))

    def test_schema_json_validation(self):
        schema_path = REPO / "tools" / "schema.json"
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        validator = jsonschema.Draft202012Validator(schema)

        valid_storage = {
            "slug": "filecoin-onchain-cloud-warm-storage",
            "provider": "filecoin",
            "toolType": "Storage",
            "price": "$0.005/GB",
            "tag": ["Filecoin", "Decentralized"],
            "description": "Onchain cloud warm storage with PDP verification",
            "starred": False,
            "actionButtons": ["[Website](https://filecoin.io)"],
            "planType": "Pay-as-you-go",
            "possessionProofMechanisms": ["PDP"]
        }

        storage_schema = schema["$defs"]["storages"]
        storage_validator = jsonschema.Draft202012Validator(storage_schema)
        self.assertTrue(storage_validator.is_valid(valid_storage))

        invalid_storage = dict(valid_storage)
        invalid_storage["possessionProofMechanisms"] = ["InvalidMechanism"]
        self.assertFalse(storage_validator.is_valid(invalid_storage))


if __name__ == "__main__":
    unittest.main()
