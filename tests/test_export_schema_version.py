import json
import sqlite3
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import create_ndjson
import create_sqlite


class ExportSchemaVersionTests(unittest.TestCase):
    def test_versions_survive_archive_and_database_exports(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            schema = root / "schema.json"
            schema.write_text('{"properties": {}, "$defs": {}}', encoding="utf-8")
            with patch.object(create_ndjson, "JSON_DIR", name):
                for network, version in [("first", "2.0.0"), ("second", "3.0.0"), ("legacy", None)]:
                    raw = {"meta": {"categories": {"apis": {"label": "APIs"}}}}
                    if version is not None:
                        raw["schemaVersion"] = version
                    create_ndjson.write_tar(network, raw)
            with tarfile.open(root / "first-ndjson.tar.gz") as archive:
                self.assertIn("meta/document.ndjson", archive.getnames())
                self.assertEqual(json.load(archive.extractfile("meta/document.ndjson")),
                                 {"schemaVersion": "2.0.0"})
            with patch.object(create_sqlite, "SCHEMA_FILE", str(schema)), \
                 patch.object(create_sqlite, "DATA_DIR", root):
                create_sqlite.main()
            for network, expected in [("app", [("first", "2.0.0"), ("second", "3.0.0")]),
                                      ("first", [("first", "2.0.0")]), ("legacy", [])]:
                db = root / f"{network}.db"
                with tarfile.open(root / f"{network}.db.tar.gz") as archive:
                    db.write_bytes(archive.extractfile(db.name).read())
                conn = sqlite3.connect(db)
                try:
                    self.assertEqual(conn.execute(
                        'SELECT network, schemaVersion FROM __meta_documents ORDER BY network'
                    ).fetchall(), expected)
                finally:
                    conn.close()


if __name__ == "__main__":
    unittest.main()
