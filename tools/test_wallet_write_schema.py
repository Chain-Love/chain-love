import json
from pathlib import Path

from jsonschema import Draft202012Validator


SCHEMA = json.loads((Path(__file__).parent / "schema.json").read_text())
WALLET_CATEGORIES = ("services", "mcpservers", "platforms")


def _validator(category):
    return Draft202012Validator(SCHEMA["$defs"][category])


def _valid_item(category):
    if category == "services":
        return {
            "slug": "example-service",
            "provider": "example-provider",
            "toolType": "api",
            "price": None,
            "tag": None,
            "description": None,
            "starred": False,
            "actionButtons": None,
            "planType": "Free",
        }

    if category == "mcpservers":
        return {
            "slug": "example-mcp-server",
            "provider": "example-provider",
            "offer": None,
            "actionButtons": None,
            "serverType": "server",
            "hostingType": "hosted",
            "transportType": "http",
            "mcpEndpoint": None,
            "authType": "none",
            "credentialKey": None,
            "selfHostedCommand": None,
            "selfHostedArgs": None,
            "selfHostedRequiredEnvVars": None,
            "x402": False,
            "onChainWrite": False,
            "agentSkills": None,
            "tag": None,
            "description": None,
            "planType": "Free",
            "price": None,
            "trial": False,
            "starred": False,
        }

    if category == "platforms":
        return {
            "slug": "example-platform",
            "provider": "example-provider",
            "actionButtons": None,
            "toolType": "platform",
            "description": None,
            "tag": None,
            "planType": "Free",
            "planName": None,
            "price": "Free",
            "trial": False,
            "availableApis": None,
            "executionEnvironment": None,
        }

    raise AssertionError(f"Unhandled category: {category}")


def _errors(category, item):
    return list(_validator(category).iter_errors(item))


def test_wallet_connection_allows_reviewed_values_and_null():
    for category in WALLET_CATEGORIES:
        for value in ("none", "optional", "required", "unknown", None):
            item = _valid_item(category)
            item["walletConnection"] = value
            assert not _errors(category, item), (category, value)


def test_wallet_connection_rejects_unreviewed_values():
    for category in WALLET_CATEGORIES:
        item = _valid_item(category)
        item["walletConnection"] = "sometimes"
        assert _errors(category, item), category


def test_wallet_connection_remains_optional_for_incremental_backfill():
    for category in WALLET_CATEGORIES:
        item = _valid_item(category)
        assert not _errors(category, item), category


def test_on_chain_write_types_match_category_requirements():
    for category in ("services", "platforms"):
        for value in (True, False, None):
            item = _valid_item(category)
            item["onChainWrite"] = value
            assert not _errors(category, item), (category, value)

    mcp_server = _valid_item("mcpservers")
    mcp_server["onChainWrite"] = True
    assert not _errors("mcpservers", mcp_server)

    mcp_server["onChainWrite"] = None
    assert _errors("mcpservers", mcp_server)


def test_on_chain_write_rejects_string_booleans():
    for category in WALLET_CATEGORIES:
        item = _valid_item(category)
        item["onChainWrite"] = "true"
        assert _errors(category, item), category


if __name__ == "__main__":
    test_wallet_connection_allows_reviewed_values_and_null()
    test_wallet_connection_rejects_unreviewed_values()
    test_wallet_connection_remains_optional_for_incremental_backfill()
    test_on_chain_write_types_match_category_requirements()
    test_on_chain_write_rejects_string_booleans()
