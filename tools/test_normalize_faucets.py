#!/usr/bin/env python3
"""Tests for faucet normalization script."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from normalize_faucets import (  # noqa: E402
    normalize_faucet_row,
    parse_amount_and_asset,
    parse_period,
)


def test_parse_period_hours() -> None:
    """Parse '24h' to 86400 seconds."""
    assert parse_period("24h") == 86400


def test_parse_period_seconds() -> None:
    """Parse '10sec' to 10 seconds."""
    assert parse_period("10sec") == 10


def test_parse_period_bare_number() -> None:
    """Bare number assumed to be hours."""
    assert parse_period("24") == 86400


def test_parse_period_empty() -> None:
    """Empty string returns None."""
    assert parse_period("") is None


def test_parse_period_null() -> None:
    """Literal NULL returns None."""
    assert parse_period("NULL") is None


def test_parse_amount_simple() -> None:
    """Parse '0.1 ETH' to one entry."""
    result = parse_amount_and_asset("0.1 ETH")
    assert len(result) == 1
    assert result[0] == ("0.1", "ETH", None)


def test_parse_amount_alphanumeric() -> None:
    """Parse '100 tFIL' to one entry with alphanumeric asset."""
    result = parse_amount_and_asset("100 tFIL")
    assert len(result) == 1
    assert result[0] == ("100", "TFIL", None)


def test_parse_amount_multi_tier() -> None:
    """Parse '0.5/1/2.5/5 SOL' to four entries."""
    result = parse_amount_and_asset("0.5/1/2.5/5 SOL")
    assert len(result) == 4
    assert result[0] == ("0.5", "SOL", None)
    assert result[3] == ("5", "SOL", None)


def test_parse_amount_up_to() -> None:
    """Parse 'up to 1 TON' with condition."""
    result = parse_amount_and_asset("up to 1 TON")
    assert len(result) == 1
    assert result[0] == ("1", "TON", "maximum")


def test_parse_amount_compound() -> None:
    """Parse '0.1 ETH/1 ETH72h' to two entries."""
    result = parse_amount_and_asset("0.1 ETH/1 ETH72h")
    assert len(result) == 2
    assert result[0] == ("0.1", "ETH", None)
    assert result[1] == ("1", "ETH72H", None)


def test_parse_amount_empty() -> None:
    """Empty string returns empty list."""
    assert parse_amount_and_asset("") == []


def test_parse_amount_bare_number() -> None:
    """Bare number uses default asset."""
    result = parse_amount_and_asset("0.001")
    assert len(result) == 1
    assert result[0] == ("0.001", "ETH", None)


def test_normalize_alchemy() -> None:
    """Full normalization of alchemy-faucet row."""
    row = {
        "slug": "alchemy-faucet",
        "dripLimitAmount": "0.1 ETH",
        "dripLimitPeriod": "24h",
    }
    result = normalize_faucet_row(row)
    assert result is not None
    parsed = json.loads(result)
    assert len(parsed) == 1
    assert parsed[0]["amount"] == "0.1"
    assert parsed[0]["asset"] == "ETH"
    assert parsed[0]["cooldownSeconds"] == 86400


def test_normalize_core() -> None:
    """Full normalization of core-faucet (tCORE2)."""
    row = {
        "slug": "core-faucet",
        "dripLimitAmount": "1 tCORE2",
        "dripLimitPeriod": "24h",
    }
    result = normalize_faucet_row(row)
    assert result is not None
    parsed = json.loads(result)
    assert parsed[0]["asset"] == "TCORE2"


def test_normalize_empty() -> None:
    """Empty row returns empty string."""
    row = {"slug": "empty-faucet", "dripLimitAmount": "", "dripLimitPeriod": ""}
    assert normalize_faucet_row(row) == ""


def test_normalize_no_amount() -> None:
    """Period without amount returns empty."""
    row = {"slug": "no-amount", "dripLimitAmount": "", "dripLimitPeriod": "24h"}
    assert normalize_faucet_row(row) == ""


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
