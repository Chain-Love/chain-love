from __future__ import annotations
import builtins
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools import create_ndjson

_ORIGINAL_OPEN = builtins.open

def _legacy_open(*args, **kwargs):
    mode = args[1] if len(args) > 1 else kwargs.get("mode", "r")
    if "b" not in mode and kwargs.get("encoding") is None:
        kwargs["encoding"] = "cp1252"
    return _ORIGINAL_OPEN(*args, **kwargs)

class JsonInputEncodingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "sample.json"
    def write(self, value):
        self.path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    def read(self):
        with patch("builtins.open", side_effect=_legacy_open):
            return create_ndjson.load_raw_json(str(self.path))

    def test_unicode_values_survive_legacy_default_encoding(self):
        expected = {"apis": [{"price": "€200/month", "note": "BTC → ETH", "display": "Rīga · 日本語"}]}
        self.write(expected)
        self.assertEqual(self.read(), expected)
    def test_ascii_values_and_json_types_unchanged(self):
        expected = {"apis": [{"slug": "demo", "enabled": True, "count": 12, "price": None, "tags": ["one", "two"]}]}
        self.write(expected)
        self.assertEqual(self.read(), expected)
    def test_ndjson_archive_preserves_unicode(self):
        expected = {"apis": [{"price": "€200/month", "note": "BTC → ETH"}], "columns": {"apis": ["price", "note"]}}
        self.write(expected)
        with patch.object(create_ndjson, "JSON_DIR", self.temp.name):
            create_ndjson.write_tar("sample", self.read())
        with tarfile.open(Path(self.temp.name) / "sample-ndjson.tar.gz", "r:gz") as archive:
            payload = archive.extractfile("apis.ndjson")
            self.assertIsNotNone(payload)
            record = json.loads(payload.read().decode("utf-8").strip())
        self.assertEqual(record, expected["apis"][0])
    def test_invalid_utf8_rejected(self):
        self.path.write_bytes(b'{"apis":[{"note":"\xff"}]}')
        with self.assertRaises(UnicodeDecodeError):
            self.read()
    def test_non_object_json_root_rejected(self):
        self.path.write_text("[]", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "expected object"):
            self.read()
