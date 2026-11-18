"""Sibling of tools/test_create_ndjson_utf8.py.

validate.py and create_sqlite.py read the same UTF-8 JSON that csv_to_json.py
writes. On a legacy locale, open() without an encoding corrupts non-ASCII
before json.load sees it.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import create_sqlite, validate

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


class JsonUtf8ReaderTests(unittest.TestCase):
    def test_validate_load_json_preserves_non_ascii_on_legacy_locale(self) -> None:
        expected = {"apis": [{"price": "\u20ac200/month", "note": "BTC \u2192 ETH"}]}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "network.json"
            path.write_text(json.dumps(expected, ensure_ascii=False), encoding="utf-8")
            with patch("builtins.open", _legacy_locale_open_real):
                actual = validate.load_json(str(path))
        self.assertEqual(actual, expected)

    def test_validate_load_json_rejects_invalid_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.json"
            path.write_bytes(b'{"note":"\xff"}')
            with self.assertRaises(UnicodeDecodeError):
                validate.load_json(str(path))

    def test_sqlite_schema_preserves_non_ascii_on_legacy_locale(self) -> None:
        expected = {"title": "Fichier \u20ac", "type": "object"}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "schema.json"
            path.write_text(json.dumps(expected, ensure_ascii=False), encoding="utf-8")
            with patch.object(create_sqlite, "SCHEMA_FILE", str(path)):
                with patch("builtins.open", _legacy_locale_open_real):
                    actual = create_sqlite.load_schema()
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
