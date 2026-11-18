"""Regression checks for SDK release metadata without external HTTP calls."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import update_sdks_metadata_github as github
import update_sdks_metadata_npm as npm


class GitHubReleaseTagTests(unittest.TestCase):
    def setUp(self):
        github._repo_meta_cache.clear()

    def test_package_qualified_repository_tag_is_stable(self):
        releases = [
            {"tag_name": "other-package@9.0.0"},
            {"tag_name": "viem@2.57.20", "published_at": "2026-11-15T00:00:00Z"},
            {"tag_name": "viem@2.57.19"},
        ]
        chosen = github.pick_latest_stable_release(releases, repo_name="viem")
        self.assertEqual(chosen["tag_name"], "viem@2.57.20")

        client = Mock()
        client.repo.return_value = {
            "owner": {"login": "wevm"}, "license": {"spdx_id": "MIT"}
        }
        client.releases.return_value = releases
        actual = github.compute_from_github(client, "wevm/viem")
        self.assertEqual(actual["latestKnownVersion"], "viem@2.57.20")
        self.assertEqual(actual["latestKnownReleaseDate"], "2026-11-15")
        self.assertEqual(actual["maintainer"], "wevm")

    def test_unrelated_monorepo_package_tag_not_mistaken_for_sdk(self):
        releases = [
            {"tag_name": "@ledgerhq/live-desktop@4.28.0"},
            {"tag_name": "live-mobile@4.28.0"},
        ]
        self.assertIsNone(
            github.pick_latest_stable_release(releases, repo_name="ledger-live")
        )

    def test_existing_plain_semver_behavior_preserved(self):
        releases = [
            {"tag_name": "v2.0.0-rc.1"},
            {"tag_name": "v1.9.0", "published_at": "2026-10-20T00:00:00Z"},
        ]
        self.assertEqual(
            github.pick_latest_stable_release(releases, repo_name="any")["tag_name"],
            "v1.9.0",
        )


class NpmPackageUrlTests(unittest.TestCase):
    def test_registry_version_endpoint_resolves_package(self):
        cases = {
            "https://registry.npmjs.org/@somnia-chain/contracts-sdk/latest":
                "@somnia-chain/contracts-sdk",
            "https://registry.npmjs.org/@somnia-chain%2Fcontracts-sdk/latest":
                "@somnia-chain/contracts-sdk",
            "https://registry.npmjs.org/lodash/latest": "lodash",
            "https://registry.npmjs.org/@somnia-chain/contracts-sdk/0.3.0":
                "@somnia-chain/contracts-sdk",
            "https://www.npmjs.com/package/@ledgerhq/hw-app-algorand":
                "@ledgerhq/hw-app-algorand",
        }
        for url, expected in cases.items():
            with self.subTest(url=url):
                self.assertEqual(npm.normalize_npm_package(url), expected)

    def test_registry_version_url_fetches_full_metadata(self):
        package = npm.normalize_npm_package(
            "https://registry.npmjs.org/@somnia-chain/contracts-sdk/latest"
        )
        http = Mock()
        http.get_json.return_value = (
            200,
            {"dist-tags": {"latest": "2.7.0"},
             "versions": {"2.7.0": {}},
             "time": {"2.7.0": "2026-11-15T00:00:00Z"}},
            {},
        )
        client = npm.Npm(http, None)
        result = npm.compute_from_npm(client, package)
        self.assertEqual(result["latestKnownVersion"], "2.7.0")
        self.assertEqual(result["latestKnownReleaseDate"], "2026-11-15")
        self.assertEqual(
            http.get_json.call_args.args[0],
            "https://registry.npmjs.org/@somnia-chain/contracts-sdk",
        )


class NpmFallbackTests(unittest.TestCase):
    def setUp(self):
        npm._npm_cache.clear()

    def run_updater(self, sdk, meta):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "test.json"
            file.write_text(json.dumps({"sdks": [sdk]}), encoding="utf-8")
            with (
                patch.object(npm, "Http"),
                patch.object(npm, "Npm"),
                patch.object(npm, "compute_from_npm", return_value=meta) as fetch,
                patch.object(sys, "argv", [
                    "update_sdks_metadata_npm.py", "--jsonfile", "test",
                    "--json-dir", folder,
                ]),
            ):
                code = npm.main()
            return code, json.loads(file.read_text(encoding="utf-8"))["sdks"][0], fetch.call_count

    def test_github_and_npm_backfills_only_unresolved_fields(self):
        sdk = {
            "slug": "ledger-algorand-sdk",
            "actionButtons": [
                "[GitHub](https://github.com/LedgerHQ/ledger-live)",
                "[npm](https://www.npmjs.com/package/@ledgerhq/hw-app-algorand)",
            ],
            "latestKnownVersion": "TBD",
            "latestKnownReleaseDate": None,
            "maintainer": "LedgerHQ",
            "license": "",
        }
        meta = {
            "latestKnownVersion": "6.37.0",
            "latestKnownReleaseDate": "2026-11-02",
            "maintainer": "someone_else",
            "license": "Apache-2.0",
        }
        code, updated, call_count = self.run_updater(sdk, meta)
        self.assertEqual(code, 0)
        self.assertEqual(call_count, 1)
        self.assertEqual(updated["latestKnownVersion"], "6.37.0")
        self.assertEqual(updated["latestKnownReleaseDate"], "2026-11-02")
        self.assertEqual(updated["maintainer"], "LedgerHQ")
        self.assertEqual(updated["license"], "Apache-2.0")

    def test_complete_github_metadata_not_overwritten(self):
        sdk = {
            "slug": "example",
            "actionButtons": [
                "[GitHub](https://github.com/example/repo)",
                "[npm](https://www.npmjs.com/package/example)",
            ],
            "latestKnownVersion": "v2.0.0",
            "latestKnownReleaseDate": "2026-10-01",
            "maintainer": "existing",
            "license": "MIT",
        }
        code, updated, call_count = self.run_updater(
            sdk, {"latestKnownVersion": "v2.0.1"}
        )
        self.assertEqual(code, 0)
        self.assertEqual(call_count, 0)
        self.assertEqual(updated, sdk)

    def test_npm_only_packages_keep_existing_update_behavior(self):
        sdk = {
            "slug": "npm-only",
            "actionButtons": ["[npm](https://www.npmjs.com/package/example)"],
            "latestKnownVersion": "1.0.0",
        }
        code, updated, call_count = self.run_updater(
            sdk, {"latestKnownVersion": "2.0.0"}
        )
        self.assertEqual(code, 0)
        self.assertEqual(call_count, 1)
        self.assertEqual(updated["latestKnownVersion"], "2.0.0")


if __name__ == "__main__":
    unittest.main()
