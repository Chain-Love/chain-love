"""Offline schema and CSV pipeline regression tests for DBIP #2625."""

import contextlib
import csv
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from jsonschema import Draft202012Validator

import csv_to_json
import validate
import validate_csv


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "tools/schema.json").read_text(encoding="utf-8"))
CATEGORIES = json.loads((ROOT / "meta/categories.json").read_text(encoding="utf-8"))
COLUMNS = json.loads((ROOT / "meta/columns.json").read_text(encoding="utf-8"))


def compute_row():
    # Synthetic data, not a claim about any provider's current products.
    return {
        "slug": "example-compute",
        "provider": "Example Compute",
        "offer": "Example CPU",
        "actionButtons": [],
        "tag": [],
        "description": "Synthetic compute offer",
        "price": "Example price per hour",
        "planType": "Pay-as-you-go",
        "planName": None,
        "starred": False,
        "resourceTypes": ["cpu"],
        "provisioningMode": "bare_metal",
        "workloadTypes": ["general_compute", "ai_inference"],
        "hardwareModels": ["Example CPU"],
        "interfaces": ["api", "cli"],
        "pricingUnit": "hour",
        "minimumCommitment": None,
    }


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                key: json.dumps(value) if isinstance(value, (list, bool))
                else "" if value is None else value
                for key, value in row.items()
            })


class ComputeSchemaTests(unittest.TestCase):
    def setUp(self):
        self.validator = Draft202012Validator(SCHEMA)

    def test_schema_and_category_registration(self):
        Draft202012Validator.check_schema(SCHEMA)
        categories = set(SCHEMA["properties"]) - {"schemaVersion", "columns", "meta"}
        self.assertEqual(categories, set(CATEGORIES))
        self.assertEqual(categories, set(SCHEMA["$defs"]["columns"]["properties"]))
        self.assertEqual(categories, set(
            SCHEMA["$defs"]["providerMeta"]["properties"]["categories"]["items"]["enum"]
        ))
        self.assertEqual(CATEGORIES["compute"]["key"], "compute")

    def test_compute_metadata_and_column_order(self):
        keys = list(compute_row())
        self.assertEqual(set(keys), set(SCHEMA["$defs"]["compute"]["properties"]))
        for key in keys:
            with self.subTest(key=key):
                self.assertEqual(COLUMNS[key]["key"], key)
        data = {"columns": {"compute": keys}, "meta": {
            "categories": CATEGORIES, "columns": COLUMNS,
            "providers": {"example-compute": {
                "slug": "example-compute", "name": "Example Compute",
                "starred": False, "categories": ["compute"],
            }},
        }}
        self.validator.validate(data)
        self.assertEqual(validate.rule_meta_categories_consistent(data), [])
        self.assertEqual(validate.rule_meta_columns_consistent(data), [])

    def test_complete_row_and_nullable_fields(self):
        row = compute_row()
        self.validator.validate({"compute": [row]})
        for key in row:
            if key not in {"slug", "provider", "planType", "starred"}:
                row[key] = None
        self.validator.validate({"compute": [row]})

    def test_required_headers(self):
        for key in compute_row():
            with self.subTest(key=key):
                row = compute_row()
                del row[key]
                self.assertFalse(self.validator.is_valid({"compute": [row]}))

    def test_supported_enum_values(self):
        values = {
            "resourceTypes": ["cpu", "gpu", "accelerator"],
            "provisioningMode": ["container", "vm", "bare_metal", "serverless", "marketplace", "mixed"],
            "workloadTypes": ["general_compute", "ai_inference", "ai_training", "rendering", "batch", "scientific"],
            "interfaces": ["web", "api", "cli", "docker", "kubernetes", "sdk"],
            "pricingUnit": ["hour", "second", "job", "market-based"],
        }
        for key, choices in values.items():
            for choice in choices:
                with self.subTest(key=key, value=choice):
                    row = compute_row()
                    row[key] = [choice] if isinstance(row[key], list) else choice
                    self.validator.validate({"compute": [row]})

    def test_reject_unknown_enum_values_wrong_types_and_duplicates(self):
        for key in ["resourceTypes", "provisioningMode", "workloadTypes", "interfaces", "pricingUnit"]:
            bad_values = [["unknown"], "unknown", True, 1, {}]
            if isinstance(compute_row()[key], list):
                bad_values.append(compute_row()[key] * 2)
            for value in bad_values:
                with self.subTest(key=key, value=value):
                    row = compute_row()
                    row[key] = value
                    self.assertFalse(self.validator.is_valid({"compute": [row]}))

    def test_hardware_models_do_not_repurpose_wallet_hardware(self):
        self.assertEqual(SCHEMA["$defs"]["wallets"]["properties"]["hardware"], {"type": "boolean"})
        self.assertEqual(COLUMNS["hardware"]["description"], "Supports hardware wallets.")
        self.assertEqual(COLUMNS["hardware"]["sorting"], "boolean")
        for value in [True, "Example CPU", [True]]:
            row = compute_row()
            row["hardwareModels"] = value
            self.assertFalse(self.validator.is_valid({"compute": [row]}))
        row = compute_row()
        row["hardware"] = True
        self.assertFalse(self.validator.is_valid({"compute": [row]}))

    def test_unknown_fields_and_category_rejected(self):
        row = compute_row()
        row["unknown"] = "value"
        self.assertFalse(self.validator.is_valid({"compute": [row]}))
        self.assertFalse(self.validator.is_valid({"unknownCategory": []}))

    def test_snake_case_is_not_unclosed_emphasis(self):
        for value in ["bare_metal", "general_compute", "uses bare_metal capacity", "_bare_metal_", "`bare_metal`"]:
            with self.subTest(value=value):
                self.assertFalse(validate.has_unclosed_markdown(value))
        self.assertEqual(validate.rule_no_unclosed_markdown([compute_row()]), [])

    def test_unclosed_markdown_still_rejected(self):
        for value in ["_unclosed", "unclosed_", "_bare_metal", "*unclosed", "**unclosed", "`unclosed", "[unclosed", "(unclosed"]:
            with self.subTest(value=value):
                self.assertTrue(validate.has_unclosed_markdown(value))

    def test_csv_generation_inheritance_override_and_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / "meta", root / "meta")
            shutil.copyfile(ROOT / "tools/schema.json", root / "schema.json")
            row = compute_row()
            fields = list(row)
            write_csv(root / "references/providers/providers.csv", ["slug", "name", "starred"], [{
                "slug": "example-compute", "name": "Example Compute", "starred": False,
            }])
            specific = {**row, "slug": "example-specific", "offer": "Example GPU"}
            write_csv(root / "references/offers/compute.csv", fields, [row, specific])
            write_csv(root / "listings/all-networks/compute.csv", fields, [{
                "slug": "example-global", "offer": "!offer:example-compute",
            }])
            write_csv(root / "listings/specific-networks/example-one/compute.csv", fields, [{
                "slug": "example-override", "offer": "!offer:example-specific",
                "price": "Synthetic network override", "resourceTypes": ["gpu"],
            }])
            (root / "listings/specific-networks/example-two").mkdir(parents=True)
            previous = Path.cwd()
            try:
                os.chdir(root)
                with contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises(SystemExit) as result:
                        validate_csv.main()
                    self.assertEqual(result.exception.code, 0)
                    csv_to_json.main()
                    validate.main()
            finally:
                os.chdir(previous)
            generated = sorted((root / "json").glob("*.json"))
            self.assertEqual(len(generated), 2)
            data = json.loads(generated[0].read_text(encoding="utf-8"))
            self.assertEqual(len(data["compute"]), 2)
            override, inherited = data["compute"]
            self.assertEqual(override["price"], "Synthetic network override")
            self.assertEqual(override["resourceTypes"], ["gpu"])
            self.assertEqual(inherited["provisioningMode"], "bare_metal")
            self.assertEqual(inherited["offer"], "Example CPU")
            self.assertEqual(data["columns"]["compute"], fields)
            self.assertEqual(data["meta"]["providers"]["example-compute"]["categories"], ["compute"])
            for path in generated:
                self.validator.validate(json.loads(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
