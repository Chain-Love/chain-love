import json
import tempfile
from pathlib import Path

from validate import load_chain_validation_allowlist, rule_chain_values_consistent


def _errors(item, *, network="example", allowlist=None):
    return rule_chain_values_consistent(
        [item],
        {
            "network": network,
            "allowlist": allowlist or set(),
        },
    )


def test_exact_chain_signal_matches():
    assert not _errors({"slug": "rpc-sepolia", "chain": "sepolia"})


def test_slug_signal_mismatch_fails():
    errors = _errors({"slug": "rpc-sepolia", "chain": "mainnet"})

    assert errors
    assert "sepolia" in errors[0]


def test_generic_testnet_matches_specific_testnet_signals():
    assert not _errors({"slug": "rpc-sepolia", "chain": "testnet"})


def test_mainnet_signal_matches_network_canonical_chain():
    assert not _errors({"slug": "subscan-mainnet", "chain": "astar"}, network="astar")


def test_network_specific_mainnet_aliases_are_not_global():
    assert not _errors({"slug": "rpc-mainnet", "chain": "one"}, network="arbitrum")
    assert _errors({"slug": "rpc-mainnet", "chain": "one"}, network="example")


def test_url_signal_is_checked_even_when_slug_has_signal():
    errors = _errors(
        {
            "slug": "rpc-mainnet",
            "chain": "mainnet",
            "actionButtons": ["[Docs](https://example.com/docs/sepolia)"],
        }
    )

    assert errors
    assert "sepolia" in errors[0]


def test_chain_family_names_are_not_generic_mainnet_aliases():
    errors = _errors({"slug": "rpc-mainnet", "chain": "one"})

    assert errors
    assert "mainnet" in errors[0]


def test_allowlist_suppresses_exact_documented_exception():
    item = {"slug": "rpc-sepolia", "chain": "mainnet"}

    assert _errors(item, network="example")
    assert not _errors(item, network="example", allowlist={"example/rpc-sepolia"})


def test_allowlist_requires_non_empty_reasons():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "allowlist.json"

        path.write_text(json.dumps({"entries": ["example/rpc-sepolia"]}))
        try:
            load_chain_validation_allowlist(path)
        except ValueError as exc:
            assert "entries" in str(exc)
        else:
            raise AssertionError("list-style allowlist entries must be rejected")

        path.write_text(
            json.dumps(
                {"entries": {"example/rpc-sepolia": "intentional cross-network docs link"}}
            )
        )
        assert load_chain_validation_allowlist(path) == {"example/rpc-sepolia"}


def main():
    test_exact_chain_signal_matches()
    test_slug_signal_mismatch_fails()
    test_generic_testnet_matches_specific_testnet_signals()
    test_mainnet_signal_matches_network_canonical_chain()
    test_network_specific_mainnet_aliases_are_not_global()
    test_url_signal_is_checked_even_when_slug_has_signal()
    test_chain_family_names_are_not_generic_mainnet_aliases()
    test_allowlist_suppresses_exact_documented_exception()
    test_allowlist_requires_non_empty_reasons()


if __name__ == "__main__":
    main()
