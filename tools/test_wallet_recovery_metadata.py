#!/usr/bin/env python3
"""Focused checks for wallet recovery metadata schema additions."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator


SCHEMA = json.loads(Path("tools/schema.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA["$defs"]["wallets"])


BASE_WALLET = {
    "slug": "example-wallet",
    "provider": "Example",
    "offer": None,
    "openSource": False,
    "supportedPlatforms": ["Web"],
    "custodial": False,
    "mfa": False,
    "msig": False,
    "hardware": False,
    "keyExport": True,
    "native": False,
    "evm": True,
    "tendermint": False,
    "tokensSupport": ["ERC-20"],
    "staking": False,
    "price": None,
    "support": None,
    "audit": None,
    "languages": None,
    "starred": False,
    "actionButtons": ["[Website](https://example.com)"],
    "tag": None,
}


def assert_valid(**updates: object) -> None:
    wallet = copy.deepcopy(BASE_WALLET)
    wallet.update(updates)
    errors = sorted(VALIDATOR.iter_errors(wallet), key=lambda error: error.path)
    assert not errors, [error.message for error in errors]


def assert_invalid(**updates: object) -> None:
    wallet = copy.deepcopy(BASE_WALLET)
    wallet.update(updates)
    errors = list(VALIDATOR.iter_errors(wallet))
    assert errors, "expected schema validation to fail"


def test_recovery_methods_accept_known_enum_values() -> None:
    assert_valid(recoveryMethods=["seed_phrase"], recoveryDelay="0")
    assert_valid(
        recoveryMethods=["passkey", "social_guardians"],
        recoveryDelay="48h",
    )
    assert_valid(recoveryMethods=["multisig", "hardware_backup"], recoveryDelay=None)
    assert_valid(recoveryMethods=["unknown"], recoveryDelay=None)


def test_recovery_methods_reject_unknown_values_duplicates_and_none_combos() -> None:
    assert_invalid(recoveryMethods=["mnemonic"], recoveryDelay=None)
    assert_invalid(recoveryMethods=["seed_phrase", "seed_phrase"], recoveryDelay=None)
    assert_invalid(recoveryMethods=["none", "seed_phrase"], recoveryDelay=None)


def test_recovery_delay_format() -> None:
    assert_valid(recoveryMethods=["seed_phrase"], recoveryDelay="1m")
    assert_valid(recoveryMethods=["seed_phrase"], recoveryDelay="24h")
    assert_valid(recoveryMethods=["seed_phrase"], recoveryDelay="7d")
    assert_invalid(recoveryMethods=["seed_phrase"], recoveryDelay="01h")
    assert_invalid(recoveryMethods=["seed_phrase"], recoveryDelay="2w")
    assert_invalid(recoveryMethods=["seed_phrase"], recoveryDelay="fast")


if __name__ == "__main__":
    test_recovery_methods_accept_known_enum_values()
    test_recovery_methods_reject_unknown_values_duplicates_and_none_combos()
    test_recovery_delay_format()
