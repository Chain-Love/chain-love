import contextlib
import io
import unittest
from unittest.mock import Mock

import update_sdks_metadata_gitlab as updater


class GitLabResponseTests(unittest.TestCase):
    def setUp(self):
        updater._gitlab_cache.clear()
        self.http = Mock()
        self.client = updater.GitLab(self.http, None)

    def test_error_responses_are_not_metadata(self):
        for method in ("project", "releases", "tags"):
            for status in (401, 403, 404, 429, 500):
                with self.subTest(method=method, status=status):
                    self.http.get_json.return_value = (status, {"message": "error"}, {})
                    with contextlib.redirect_stderr(io.StringIO()):
                        result = getattr(self.client, method)("group/sdk")
                    self.assertEqual(result, None if method == "project" else [])

    def test_list_endpoints_require_lists_of_objects(self):
        for method in ("releases", "tags"):
            for body in ({"message": "error"}, "error", None):
                with self.subTest(method=method, body=body):
                    self.http.get_json.return_value = (200, body, {})
                    self.assertEqual(getattr(self.client, method)("group/sdk"), [])
            self.http.get_json.return_value = (200, [None, "bad", {"name": "v1.0"}], {})
            self.assertEqual(getattr(self.client, method)("group/sdk"), [{"name": "v1.0"}])

    def test_release_error_can_fall_back_to_tags(self):
        self.http.get_json.side_effect = [
            (200, {"visibility": "public", "namespace": {"full_path": "group"}}, {}),
            (429, {"message": "Too Many Requests"}, {"Retry-After": "30"}),
            (200, [{"name": "v1.2.3", "commit": {"committed_date": "2026-10-20T00:00:00Z"}}], {}),
        ]
        warning = io.StringIO()
        with contextlib.redirect_stderr(warning):
            result = updater.compute_from_gitlab(self.client, "group/sdk", True)
        self.assertEqual(result["latestKnownVersion"], "v1.2.3")
        self.assertEqual(result["latestKnownReleaseDate"], "2026-10-20")
        self.assertIn("retry after 30s", warning.getvalue())

    def test_successful_release_metadata_is_preserved(self):
        self.http.get_json.side_effect = [
            (200, {"visibility": "public", "owner": {"username": "owner"}, "license": {"spdx_identifier": "MIT"}}, {}),
            (200, [{"tag_name": "v2.0.0", "released_at": "2026-10-21T00:00:00Z"}], {}),
        ]
        self.assertEqual(updater.compute_from_gitlab(self.client, "group/sdk", False), {
            "maintainer": "owner", "license": "MIT", "latestKnownVersion": "v2.0.0",
            "latestKnownReleaseDate": "2026-10-21",
        })


if __name__ == "__main__":
    unittest.main()
