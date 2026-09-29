from __future__ import annotations

import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import create_ndjson


# Keep a handle to the real open before any patching.
_real_open = open


def _legacy_locale_open_real(
    file,
    mode="r",
    buffering=-1,
    encoding=None,
    errors=None,
    newline=None,
    closefd=True,
    opener=None,
):
    if "b" not in mode and encoding is None:
        encoding = "cp1252"
    return _real_open(
        file,
        mode,
        buffering,
        encoding,
        errors,
        newline,
        closefd,
        opener,
    )


class LoadRawJsonUtf8Tests(unittest.TestCase):
    def test_preserves_non_ascii_on_legacy_locale(self) -> None:
        expected = {
            "apis": [{"price": "\u20ac200/month", "note": "BTC \u2192 ETH"}]
        }
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.json"
            path.write_text(
                json.dumps(expected, ensure_ascii=False), encoding="utf-8"
            )
            with patch("builtins.open", _legacy_locale_open_real):
                actual = create_ndjson.load_raw_json(str(path))
        self.assertEqual(actual, expected)

    def test_round_trip_archive_preserves_non_ascii(self) -> None:
        raw = {
            "apis": [{"price": "\u20ac200/month", "note": "BTC \u2192 ETH"}],
            "columns": {"apis": ["price", "note"]},
        }
        with tempfile.TemporaryDirectory() as folder:
            json_path = Path(folder) / "demo.json"
            json_path.write_text(
                json.dumps(raw, ensure_ascii=False), encoding="utf-8"
            )
            with patch.object(create_ndjson, "JSON_DIR", folder):
                with patch("builtins.open", _legacy_locale_open_real):
                    loaded = create_ndjson.load_raw_json(str(json_path))
                create_ndjson.write_tar("demo", loaded)
            archive = Path(folder) / "demo-ndjson.tar.gz"
            with tarfile.open(archive, "r:gz") as tar:
                member = tar.extractfile("apis.ndjson")
                assert member is not None
                line = member.read().decode("utf-8").strip()
            self.assertEqual(json.loads(line), raw["apis"][0])

    def test_ascii_and_json_types_unchanged(self) -> None:
        expected = {
            "apis": [
                {
                    "slug": "demo",
                    "count": 3,
                    "enabled": True,
                    "price": None,
                    "tags": ["a", "b"],
                }
            ]
        }
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.json"
            path.write_text(json.dumps(expected), encoding="utf-8")
            with patch("builtins.open", _legacy_locale_open_real):
                actual = create_ndjson.load_raw_json(str(path))
        self.assertEqual(actual, expected)

    def test_invalid_utf8_raises(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.json"
            path.write_bytes(b'{"apis":[{"note":"\xff"}]}')
            with self.assertRaises(UnicodeDecodeError):
                create_ndjson.load_raw_json(str(path))

    def test_non_object_root_raises(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "list.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "expected object"):
                create_ndjson.load_raw_json(str(path))


if __name__ == "__main__":
    unittest.main()
