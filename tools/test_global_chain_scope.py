"""Regression tests for chain-scoped global listing expansion."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from csv_to_json import expand_global_chain_rows, scoped_global_chains


class GlobalChainScopeTest(unittest.TestCase):
    CHAINS = ["betanet", "mainnet", "testnet"]

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.directory = self.tempdir.name

    def _policy(self, data):
        path = os.path.join(self.directory, "global-chain-scope.json")
        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file)

    def test_default_keeps_previous_behavior_for_other_networks(self):
        selected = scoped_global_chains(self.directory, self.CHAINS)
        self.assertEqual(selected, self.CHAINS)
        rows = expand_global_chain_rows([{"slug": "global-api"}], selected)
        self.assertEqual(
            [row["slug"] for row in rows],
            ["global-api-betanet", "global-api-mainnet", "global-api-testnet"],
        )

    def test_explicit_scope_blocks_unsupported_betanet_globals(self):
        self._policy({"chains": ["mainnet", "testnet"]})
        selected = scoped_global_chains(self.directory, self.CHAINS)
        api = expand_global_chain_rows(
            [{"slug": "1rpc-enterprise-recent-state", "technology": "EVM JSON-RPC"}],
            selected,
        )
        analytics = expand_global_chain_rows(
            [{"slug": "defillama-enterprise"}],
            selected,
        )
        self.assertEqual(
            [row["slug"] for row in api],
            ["1rpc-enterprise-recent-state-mainnet", "1rpc-enterprise-recent-state-testnet"],
        )
        self.assertEqual(
            [row["slug"] for row in analytics],
            ["defillama-enterprise-mainnet", "defillama-enterprise-testnet"],
        )
        self.assertFalse(any(row["chain"] == "betanet" for row in api + analytics))

    def test_unscoped_specific_betanet_listing_is_unaffected(self):
        self._policy({"chains": ["mainnet", "testnet"]})
        selected = scoped_global_chains(self.directory, self.CHAINS)
        local_faucets = [{"slug": "algorand-betanet-dispenser-algo", "chain": "betanet"}]
        global_api = expand_global_chain_rows([{"slug": "global-api"}], selected)
        self.assertEqual(local_faucets[0]["chain"], "betanet")
        self.assertEqual(len(global_api), 2)

    def test_empty_allowlist_blocks_all_global_chain_rows(self):
        self._policy({"chains": []})
        self.assertEqual(scoped_global_chains(self.directory, self.CHAINS), [])
        self.assertEqual(expand_global_chain_rows([{"slug": "global-api"}], []), [])

    def test_unknown_chain_fails_loudly(self):
        self._policy({"chains": ["mainnet", "fictional"]})
        with self.assertRaisesRegex(ValueError, "undeclared network chains"):
            scoped_global_chains(self.directory, self.CHAINS)

    def test_duplicates_or_invalid_chain_names_fail(self):
        for invalid in [
            {"chains": ["mainnet", "mainnet"]},
            {"chains": ["Mainnet"]},
            {"chains": [" testnet"]},
            {"chains": [123]},
            {"chains": "mainnet"},
            {"chain": ["mainnet"]},
        ]:
            with self.subTest(invalid=invalid):
                self._policy(invalid)
                with self.assertRaises(ValueError):
                    scoped_global_chains(self.directory, self.CHAINS)


if __name__ == "__main__":
    unittest.main()
