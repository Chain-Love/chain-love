import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import create_ndjson


class CreateNdjsonTests(unittest.TestCase):
    def test_failed_rebuild_preserves_existing_archive(self) -> None:
        raw = {
            "apis": [{"slug": "one"}],
            "wallets": [{"slug": "two"}],
            "columns": {"apis": ["slug"], "wallets": ["slug"]},
        }

        with tempfile.TemporaryDirectory() as directory:
            with patch.object(create_ndjson, "JSON_DIR", directory):
                create_ndjson.write_tar("demo", raw)
                target = Path(directory) / "demo-ndjson.tar.gz"
                previous_archive = target.read_bytes()

                original_write = create_ndjson.write_ndjson_file
                call_count = 0

                def fail_on_second_write(tar, name, items):
                    nonlocal call_count
                    call_count += 1
                    if call_count == 2:
                        raise OSError("simulated rebuild failure")
                    return original_write(tar, name, items)

                with patch.object(
                    create_ndjson,
                    "write_ndjson_file",
                    side_effect=fail_on_second_write,
                ), self.assertRaises(OSError):
                    create_ndjson.write_tar("demo", raw)

                self.assertEqual(target.read_bytes(), previous_archive)
                self.assertEqual(list(Path(directory).iterdir()), [target])

    def test_successful_rebuild_replaces_archive_after_close(self) -> None:
        old_raw = {"apis": [{"slug": "old"}]}
        new_raw = {
            "apis": [{"slug": "new"}],
            "columns": {"apis": ["slug"]},
            "meta": {"categories": [{"key": "apis"}]},
        }

        with tempfile.TemporaryDirectory() as directory:
            with patch.object(create_ndjson, "JSON_DIR", directory):
                create_ndjson.write_tar("demo", old_raw)
                target = Path(directory) / "demo-ndjson.tar.gz"
                previous_archive = target.read_bytes()

                create_ndjson.write_tar("demo", new_raw)

                self.assertNotEqual(target.read_bytes(), previous_archive)
                with tarfile.open(target, "r:gz") as archive:
                    self.assertEqual(
                        archive.getnames(),
                        ["apis.ndjson", "columns/apis.json", "meta/categories.ndjson"],
                    )
                    contents = archive.extractfile("apis.ndjson").read()
                self.assertEqual(contents, b'{"slug":"new"}\n')


if __name__ == "__main__":
    unittest.main()
