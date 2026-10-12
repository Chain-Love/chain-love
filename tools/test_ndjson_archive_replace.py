"""write_tar must not destroy the previous archive when a rebuild fails.

Related to Chain-Love/chain-love#3832. load_raw_json encoding is #4035
and is not covered here.
"""

from __future__ import annotations

import errno
import io
import json
import os
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import create_ndjson as exporter


def _members(archive: bytes) -> dict[str, bytes]:
    found: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        for member in tar.getmembers():
            extracted = tar.extractfile(member)
            assert extracted is not None
            found[member.name] = extracted.read()
    return found


class NdjsonArchiveReplaceTest(unittest.TestCase):
    def test_failed_rebuild_preserves_previous_archive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(exporter, "JSON_DIR", directory):
                target = os.path.join(directory, "somnia-ndjson.tar.gz")
                exporter.write_tar("somnia", {"apis": [{"slug": "old"}]})
                before = Path(target).read_bytes()

                with patch.object(
                    exporter,
                    "write_ndjson_file",
                    side_effect=OSError(errno.ENOSPC, "simulated write failure"),
                ):
                    with self.assertRaises(OSError):
                        exporter.write_tar("somnia", {"apis": [{"slug": "new"}]})

                self.assertEqual(Path(target).read_bytes(), before)
                self.assertEqual(os.listdir(directory), ["somnia-ndjson.tar.gz"])

    def test_successful_rebuild_replaces_archive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(exporter, "JSON_DIR", directory):
                target = os.path.join(directory, "somnia-ndjson.tar.gz")
                exporter.write_tar("somnia", {"apis": [{"slug": "old"}]})
                exporter.write_tar(
                    "somnia",
                    {
                        "columns": {"apis": ["slug"]},
                        "meta": {"providers": {"alchemy": {"name": "Alchemy"}}},
                        "apis": [{"slug": "new"}],
                    },
                )

                members = _members(Path(target).read_bytes())
                self.assertEqual(
                    members["apis.ndjson"],
                    (json.dumps({"slug": "new"}, separators=(",", ":")) + "\n").encode(
                        "utf-8"
                    ),
                )
                self.assertEqual(
                    members["columns/apis.json"],
                    json.dumps(["slug"], separators=(",", ":")).encode("utf-8"),
                )
                self.assertEqual(
                    json.loads(members["meta/providers.ndjson"].decode("utf-8")),
                    {"name": "Alchemy", "key": "alchemy"},
                )
                self.assertEqual(
                    sorted(members),
                    ["apis.ndjson", "columns/apis.json", "meta/providers.ndjson"],
                )
                self.assertEqual(os.listdir(directory), ["somnia-ndjson.tar.gz"])


if __name__ == "__main__":
    unittest.main()
