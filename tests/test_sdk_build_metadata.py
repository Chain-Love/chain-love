import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import update_sdks_metadata_github as github
import update_sdks_metadata_npm as npm


class BuildMetadataTests(unittest.TestCase):
    def test_stable_versions_with_build_metadata(self):
        for version in ("1.2.3", "v1.2.3", "1.2.3+001", "1.2.3+sha-5114f85",
                        "1.2.3+dev.7", "1.2.3+alpha", "v1.2.3+rc-7"):
            for check in (github.is_stable_release_tag, npm.is_stable_npm_version):
                with self.subTest(version=version, checker=check.__name__):
                    self.assertTrue(check(version))

    def test_prereleases_remain_excluded(self):
        for version in ("1.2.3-rc.1", "1.2.3-beta+sha-7", "v1.2.3-0+build.7"):
            self.assertFalse(github.is_stable_release_tag(version))
            self.assertFalse(npm.is_stable_npm_version(version))

    def test_github_preserves_release_flags_and_selects_current_version(self):
        selected = {"tag_name": "v2.0.0+sha-7", "published_at": "2026-09-14T12:00:00Z"}
        releases = [{"tag_name": "v4.0.0+build-1", "draft": True},
                    {"tag_name": "v3.0.0+build-1", "prerelease": True},
                    {"tag_name": "v3.0.0-rc.1+build-1"},
                    selected, {"tag_name": "v1.0.0"}]
        self.assertIs(github.pick_latest_stable_release(releases), selected)

    def test_github_metadata_keeps_version_and_matching_release_date(self):
        api = Mock()
        api.repo.return_value = {"owner": {"login": "example"}}
        api.releases.return_value = [
            {"tag_name": "v2.0.0+dev.7", "published_at": "2026-09-14T12:00:00Z"},
            {"tag_name": "v1.0.0", "published_at": "2026-01-01T12:00:00Z"}]
        github._repo_meta_cache.clear()
        self.addCleanup(github._repo_meta_cache.clear)
        result = github.compute_from_github(api, "example/sdk")
        self.assertEqual(result["latestKnownVersion"], "v2.0.0+dev.7")
        self.assertEqual(result["latestKnownReleaseDate"], "2026-09-14")

    def test_npm_honors_stable_latest_dist_tag(self):
        package = {"dist-tags": {"latest": "2.0.0+sha-7"},
                   "versions": {"1.0.0": {}, "2.0.0+sha-7": {}, "3.0.0": {}}}
        self.assertEqual(npm.pick_latest_stable_version(package), "2.0.0+sha-7")

    def test_npm_fallback_ignores_prereleases(self):
        package = {"dist-tags": {"latest": "3.0.0-rc.1+build-7"},
                   "versions": {"1.0.0": {}, "2.0.0+dev.7": {},
                                "3.0.0-rc.1+build-7": {}}}
        self.assertEqual(npm.pick_latest_stable_version(package), "2.0.0+dev.7")

    def test_npm_build_metadata_does_not_affect_order(self):
        self.assertEqual(npm.semver_key("1.2.3+sha-7"), npm.semver_key("1.2.3"))
        self.assertEqual(npm.semver_key("1.2.3+dev.7"), npm.semver_key("1.2.3"))

    def test_empty_and_nonnumeric_versions_remain_excluded(self):
        for version in ("", "latest", "1.x.0"):
            self.assertFalse(github.is_stable_release_tag(version))
            self.assertFalse(npm.is_stable_npm_version(version))


if __name__ == "__main__":
    unittest.main()
