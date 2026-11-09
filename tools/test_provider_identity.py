import unittest

from csv_to_json import build_provider_index_by_name, build_provider_meta_from_names


class ProviderIdentityTests(unittest.TestCase):
    def test_duplicate_slugs_with_distinct_names_are_rejected(self):
        providers = [
            {"slug": "shared-id", "name": "Provider A"},
            {"slug": "shared-id", "name": "Provider B"},
        ]
        with self.assertRaisesRegex(ValueError, "Duplicate slugs in providers.csv: shared-id"):
            build_provider_index_by_name(providers)

    def test_duplicate_names_with_distinct_slugs_are_still_rejected(self):
        providers = [
            {"slug": "provider-a", "name": "Shared Name"},
            {"slug": "provider-b", "name": "Shared Name"},
        ]
        with self.assertRaisesRegex(ValueError, "Duplicate provider name"):
            build_provider_index_by_name(providers)

    def test_distinct_provider_identities_preserve_both_profiles(self):
        providers = [
            {"slug": "provider-a", "name": "Provider A"},
            {"slug": "provider-b", "name": "Provider B"},
        ]
        index = build_provider_index_by_name(providers)
        metadata = build_provider_meta_from_names(
            index,
            {"Provider A": {"apis"}, "Provider B": {"sdks"}},
            network="algorand",
        )
        self.assertEqual(set(metadata), {"provider-a", "provider-b"})
        self.assertEqual(metadata["provider-a"]["name"], "Provider A")
        self.assertEqual(metadata["provider-b"]["categories"], ["sdks"])


if __name__ == "__main__":
    unittest.main()
