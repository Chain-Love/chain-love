import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import update_sdks_metadata_npm as npm_updater

EMAIL = "dev@example.com"


class FakeNpm:
    def __init__(self, packages):
        self.packages = packages

    def package(self, name):
        return self.packages.get(name)


def registry_doc(maintainers):
    return {
        "dist-tags": {"latest": "1.2.3"},
        "time": {"1.2.3": "2026-11-01T10:00:00.000Z"},
        "maintainers": maintainers,
        "license": "MIT",
    }


class TestNpmMaintainer(unittest.TestCase):
    def setUp(self):
        npm_updater._npm_cache.clear()

    def meta_for(self, maintainers):
        npm_updater._npm_cache.clear()
        return npm_updater.compute_from_npm(FakeNpm({"pkg": registry_doc(maintainers)}), "pkg")

    def test_name_and_email_keeps_only_the_username(self):
        meta = self.meta_for([{"name": "some_user", "email": EMAIL}, {"name": "other", "email": EMAIL}])
        self.assertEqual(meta["maintainer"], "some_user")
        self.assertNotIn("@", meta["maintainer"])
        self.assertNotIn("<", meta["maintainer"])
        self.assertNotIn(EMAIL, json.dumps(meta))
        self.assertEqual(meta["latestKnownVersion"], "1.2.3")
        self.assertEqual(meta["license"], "MIT")

    def test_name_only(self):
        self.assertEqual(self.meta_for([{"name": "someuser"}])["maintainer"], "someuser")

    def test_no_name_writes_no_maintainer(self):
        for maintainers in ([{"email": EMAIL}], [{"name": "", "email": EMAIL}], [{"name": None}], [], None):
            with self.subTest(maintainers=maintainers):
                self.assertNotIn("maintainer", self.meta_for(maintainers))

    def test_main_writes_username_and_keeps_the_built_value_without_name(self):
        fake = FakeNpm({"pkg-a": registry_doc([{"name": "user_a", "email": EMAIL}]), "pkg-b": registry_doc([{"email": EMAIL}])})
        rows = [
            {"slug": "a", "actionButtons": ["[npm](https://www.npmjs.com/package/pkg-a)"], "maintainer": "TBD"},
            {"slug": "b", "actionButtons": ["[npm](https://www.npmjs.com/package/pkg-b)"], "maintainer": "TBD"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "net.json"
            path.write_text(json.dumps({"sdks": rows}), encoding="utf-8")
            argv = ["update_sdks_metadata_npm.py", "--jsonfile", "net", "--json-dir", tmp]
            with mock.patch.object(npm_updater, "Npm", lambda http, token: fake), mock.patch("sys.argv", argv):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(npm_updater.main(), 0)
            text = path.read_text(encoding="utf-8")
        sdks = json.loads(text)["sdks"]
        self.assertEqual(sdks[0]["maintainer"], "user_a")
        self.assertEqual(sdks[1]["maintainer"], "TBD")
        self.assertEqual(sdks[1]["latestKnownVersion"], "1.2.3")
        self.assertNotIn(EMAIL, text)


if __name__ == "__main__":
    unittest.main()
