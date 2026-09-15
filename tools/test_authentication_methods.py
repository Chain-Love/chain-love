import csv
import json
import os
import tempfile
from pathlib import Path

from jsonschema import Draft202012Validator

from csv_to_json import load_csv_to_dict_list, normalize


def schema_for_apis():
    with open(Path(__file__).with_name("schema.json"), encoding="utf-8") as f:
        schema = json.load(f)
    return {
        "$schema": schema["$schema"],
        "$defs": schema["$defs"],
        "type": "object",
        "properties": {
            "apis": {
                "type": "array",
                "items": {"$ref": "#/$defs/apis"},
            }
        },
        "required": ["apis"],
        "additionalProperties": False,
    }


def assert_valid(item):
    validator = Draft202012Validator(schema_for_apis())
    errors = sorted(
        validator.iter_errors({"apis": [item]}),
        key=lambda error: list(error.absolute_path),
    )
    assert not errors, [error.message for error in errors]


def assert_invalid(item):
    validator = Draft202012Validator(schema_for_apis())
    errors = list(validator.iter_errors({"apis": [item]}))
    assert errors, "expected schema validation to fail"


def base_api_item():
    return {
        "slug": "example-api",
        "provider": "Example",
        "offer": "Example API",
        "actionButtons": None,
        "planName": "Free",
        "planType": "Free",
        "historicalData": "Recent state",
        "apiType": "RPC",
        "chain": "mainnet",
        "technology": "EVM JSON-RPC",
        "accessPrice": "$0",
        "queryPrice": "$0",
        "starred": False,
        "trial": False,
        "availableApis": None,
        "limitations": None,
        "securityImprovements": None,
        "monitoringAndAnalytics": None,
        "regions": None,
        "additionalFeatures": None,
        "address": None,
        "tag": None,
        "uptimeSla": None,
        "verifiedUptime": None,
        "blocksBehindSla": None,
        "verifiedBlocksBehindAvg": None,
        "bandwidthSla": None,
        "verifiedLatency": None,
        "supportSla": None,
    }


def test_schema_accepts_expected_authentication_methods():
    item = base_api_item()
    item["authenticationMethods"] = ["api_key", "jwt"]
    assert_valid(item)


def test_schema_allows_blank_authentication_methods():
    item = base_api_item()
    item["authenticationMethods"] = None
    assert_valid(item)


def test_schema_rejects_duplicate_authentication_methods():
    item = base_api_item()
    item["authenticationMethods"] = ["jwt", "jwt"]
    assert_invalid(item)


def test_schema_rejects_empty_authentication_methods():
    item = base_api_item()
    item["authenticationMethods"] = []
    assert_invalid(item)


def test_schema_rejects_none_combined_with_other_methods():
    item = base_api_item()
    item["authenticationMethods"] = ["none", "api_key"]
    assert_invalid(item)


def test_schema_rejects_unknown_authentication_methods():
    item = base_api_item()
    item["authenticationMethods"] = ["session_cookie"]
    assert_invalid(item)


def test_loader_pads_legacy_rows_that_omit_optional_authentication_methods():
    header = [
        "slug",
        "provider",
        "offer",
        "actionButtons",
        "planName",
        "planType",
        "historicalData",
        "apiType",
        "technology",
        "authenticationMethods",
        "accessPrice",
        "queryPrice",
        "starred",
        "trial",
        "availableApis",
        "limitations",
        "securityImprovements",
        "monitoringAndAnalytics",
        "regions",
        "additionalFeatures",
        "address",
        "tag",
        "uptimeSla",
        "verifiedUptime",
        "blocksBehindSla",
        "verifiedBlocksBehindAvg",
        "bandwidthSla",
        "verifiedLatency",
        "supportSla",
    ]
    legacy_row = [
        "legacy-api",
        "Example",
        "Legacy API",
        "",
        "Free",
        "Free",
        "Recent state",
        "RPC",
        "EVM JSON-RPC",
        "$0",
        "$0",
        "FALSE",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
    ]

    with tempfile.NamedTemporaryFile("w", newline="", delete=False) as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerow(legacy_row)
        temp_path = f.name

    try:
        data, errors = normalize({"apis": load_csv_to_dict_list(temp_path)})
    finally:
        os.unlink(temp_path)

    assert not errors
    item = data["apis"][0]
    assert item["authenticationMethods"] is None
    assert item["accessPrice"] == "$0"
    assert item["queryPrice"] == "$0"


def main():
    test_schema_accepts_expected_authentication_methods()
    test_schema_allows_blank_authentication_methods()
    test_schema_rejects_duplicate_authentication_methods()
    test_schema_rejects_empty_authentication_methods()
    test_schema_rejects_none_combined_with_other_methods()
    test_schema_rejects_unknown_authentication_methods()
    test_loader_pads_legacy_rows_that_omit_optional_authentication_methods()


if __name__ == "__main__":
    main()
