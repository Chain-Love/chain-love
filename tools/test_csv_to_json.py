import unittest

from csv_to_json import validate_no_offer_reference_conflicts


class OfferReferenceConflictTests(unittest.TestCase):
    def test_rejects_duplicate_offer_and_chain_in_network_scope(self):
        with self.assertRaisesRegex(ValueError, "foo.*mainnet.*foo-a.*foo-b"):
            validate_no_offer_reference_conflicts(
                "apis",
                "example-network",
                [
                    {"slug": "foo-a", "offer": "!offer:foo", "chain": "mainnet"},
                    {"slug": "foo-b", "offer": "!offer:foo", "chain": "mainnet"},
                ],
                [],
            )

    def test_rejects_duplicate_offer_and_chain_in_all_network_scope(self):
        with self.assertRaisesRegex(ValueError, "all-networks.*foo.*mainnet"):
            validate_no_offer_reference_conflicts(
                "apis",
                "example-network",
                [],
                [
                    {"slug": "foo-a", "offer": "!offer:foo", "chain": "mainnet"},
                    {"slug": "foo-b", "offer": "!offer:foo", "chain": "mainnet"},
                ],
            )

    def test_accepts_same_offer_on_different_chains(self):
        validate_no_offer_reference_conflicts(
            "apis",
            "example-network",
            [
                {"slug": "foo-mainnet", "offer": "!offer:foo", "chain": "mainnet"},
                {"slug": "foo-testnet", "offer": "!offer:foo", "chain": "testnet"},
            ],
            [],
        )

    def test_accepts_different_offers_on_same_chain(self):
        validate_no_offer_reference_conflicts(
            "apis",
            "example-network",
            [
                {"slug": "foo", "offer": "!offer:foo", "chain": "mainnet"},
                {"slug": "bar", "offer": "!offer:bar", "chain": "mainnet"},
            ],
            [],
        )

    def test_preserves_cross_scope_conflict_detection(self):
        with self.assertRaisesRegex(ValueError, "across listing scopes"):
            validate_no_offer_reference_conflicts(
                "apis",
                "example-network",
                [{"slug": "foo-specific", "offer": "!offer:foo", "chain": "mainnet"}],
                [{"slug": "foo-global", "offer": "!offer:foo", "chain": "mainnet"}],
            )


if __name__ == "__main__":
    unittest.main()
