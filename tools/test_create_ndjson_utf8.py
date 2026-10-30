"""Regression coverage for Chain.Love issue #4020.

Run from json-tools branch root:
    python -m unittest tools.test_create_ndjson_utf8 -v
"""
from __future__ import annotations

import builtins
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import create_ndjson


_REAL_OPEN = builtins.open


def _simulate_legacy_locale(*args, **kwargs):
    """Act like a Windows cp1252 default without overriding explicit encodings."""
    mode = args[1] if len(args) > 1 else kwargs.get("mode", "r")
    if "b" not in mode and kwargs.get("encoding") is None:
        kwargs["encoding"] = "cp1252"
    return _REAL_OPEN(*args, **kwargs)


class JsonInputEncodingTests(unittest.TestCase):
    def _read_with_legacy_default(self, path: Path):
        with patch("builtins.open", side_effect=_simulate_legacy_locale):
            return create_ndjson.load_raw_json(str(path))

    def test_unicode_values_survive_legacy_default_encoding(self):
        expected = {"apis": [{"price": "€200/month", "note": "BTC → ETH",
                               "display": "Rīga · 日本語"}]}
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "sample.json"
            source.write_text(json.dumps(expected, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(self._read_with_legacy_default(source), expected)

    def test_ascii_values_and_json_types_unchanged(self):
        expected = {"apis": [{"slug": "demo", "enabled": True, "count": 12,
                               "price": None, "tags": ["one", "two"]}]}
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "sample.json"
            source.write_text(json.dumps(expected), encoding="utf-8")
            self.assertEqual(self._read_with_legacy_default(source), expected)

    def test_ndjson_archive_preserves_unicode(self):
        expected = {"apis": [{"price": "€200/month", "note": "BTC → ETH"}],
                    "columns": {"apis": ["price", "note"]}}
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "sample.json"
            source.write_text(json.dumps(expected, ensure_ascii=False), encoding="utf-8")
            actual = self._read_with_legacy_default(source)
            with patch.object(create_ndjson, "JSON_DIR", temp):
                create_ndjson.write_tar("sample", actual)
            with tarfile.open(Path(temp) / "sample-ndjson.tar.gz", "r:gz") as archive:
                payload = archive.extractfile("apis.ndjson")
                self.assertIsNotNone(payload)
                record = json.loads(payload.read().decode("utf-8").strip())
            self.assertEqual(record, expected["apis"][0])

    def test_invalid_utf8_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "bad.json"
            source.write_bytes(b'{"apis":[{"note":"\\xff"}]}'.replace(b"\\xff", bytes([255])))
            with self.assertRaises(UnicodeDecodeError):
                self._read_with_legacy_default(source)

    def test_non_object_json_root_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "array.json"
            source.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "expected object"):
                self._read_with_legacy_default(source)


if __name__ == "__main__":
    unittest.main()
