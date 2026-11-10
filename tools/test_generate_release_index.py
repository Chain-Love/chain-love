import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().with_name("generate_release_index.py")


class GenerateReleaseIndexTests(unittest.TestCase):
    def generate(self, root: Path) -> dict:
        env = dict(os.environ, GITHUB_REPOSITORY="Chain-Love/chain-love", RELEASE_TAG="json-test")
        subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=root,
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return json.loads((root / "release-assets" / "release-index.json").read_text(encoding="utf-8"))

    def test_exact_bytes_empty_binary_and_multichunk(self):
        fixtures = {
            "empty.json": b"",
            "binary.db.tar.gz": bytes(range(256)),
            "large.json": b"x" * (1024 * 1024 + 37),
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assets_dir = root / "release-assets"
            assets_dir.mkdir()
            (assets_dir / "nested-dir").mkdir()
            for name, data in fixtures.items():
                (assets_dir / name).write_bytes(data)

            first = self.generate(root)
            self.assertEqual([a["name"] for a in first["assets"]], sorted(fixtures))
            for asset in first["assets"]:
                data = fixtures[asset["name"]]
                self.assertEqual(asset["sizeBytes"], len(data))
                self.assertEqual(asset["sha256"], hashlib.sha256(data).hexdigest())
                self.assertRegex(asset["sha256"], r"^[0-9a-f]{64}$")
                self.assertEqual(
                    asset["browser_download_url"],
                    f"https://github.com/Chain-Love/chain-love/releases/download/json-test/{asset['name']}",
                )
            self.assertEqual(first, self.generate(root))

    def test_single_asset_change_only_changes_its_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assets_dir = root / "release-assets"
            assets_dir.mkdir()
            (assets_dir / "a.json").write_bytes(b"old")
            (assets_dir / "b.json").write_bytes(b"unchanged")
            first = self.generate(root)
            (assets_dir / "a.json").write_bytes(b"new content")
            second = self.generate(root)
            self.assertNotEqual(first["assets"][0]["sha256"], second["assets"][0]["sha256"])
            self.assertNotEqual(first["assets"][0]["sizeBytes"], second["assets"][0]["sizeBytes"])
            self.assertEqual(first["assets"][1], second["assets"][1])


if __name__ == "__main__":
    unittest.main()
